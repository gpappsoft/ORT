# Copyright (c) 2025 Marco Moenig (info@moenig.it)
# 
# This software is released under the MIT License.
# https://opensource.org/licenses/MIT


import redis.asyncio as redis
import json
from loguru import logger
from cachetools import TTLCache

from app.config import settings

class RCache:
    def cache_enabled(func):
        '''Decorator to check if cache is enabled'''
        async def wrapper(*args, **kwargs):
            if not settings.CACHE_ENABLED:
                return None
            return await func(*args, **kwargs)
        return wrapper
    
    def __init__(self, 
                 host=settings.REDIS_HOST, 
                 port=settings.REDIS_PORT, 
                 db=settings.REDIS_DB, 
                 )-> None:   
        '''Initialize the Redis cache''' 
        if settings.CACHE_ENABLED and settings.CACHE_TYPE == 'redis':
            try:
                pool = redis.ConnectionPool(host=host, port=port, db=db,retry_on_timeout=True,)
                self.client = redis.StrictRedis(connection_pool=pool)
                logger.info("Redis cache initialized")

            except Exception as e:
                logger.error(f"Failed to connect to Redis: {e}")
                self.client = None

        elif settings.CACHE_ENABLED and settings.CACHE_TYPE == 'local':
            self.client = None
            self.local_cache = TTLCache(maxsize=settings.CACHE_MAXSIZE, ttl=settings.CACHE_TTL)
    
    @cache_enabled
    async def clean_cache(self,
                         )-> None:
        '''Clean the cache'''
        
        if self.client:
            try:
                await self.client.flushdb()
            except Exception as e:
                logger.error(f"Failed to clean Redis cache {e}")
        else:
            self.local_cache.clear()
            logger.info("Local cache cleaned")

    @cache_enabled
    async def set_object(self, 
                         key, 
                         obj, 
                         )-> None:
        '''Set an object in the cache'''
        
        obj_json = json.dumps(obj)
        if self.client:
            try:
                await self.client.set(key, obj_json, ex=settings.CACHE_TTL)
            except Exception as e:
                logger.error(f"Failed to set object in Redis   {e}")
        else:
            self.local_cache[key] = obj_json

    @cache_enabled
    async def get_object(self, 
                         key
                         )-> dict:
        '''Get an object from the cache'''
        
        if self.client:
            try:
                obj_json = await self.client.get(key)
            except Exception as e:
                logger.error(f"Failed to get object from Redis {e}")   
                obj_json = None
        else:
            obj_json = self.local_cache.get(key)
            
        if obj_json:
            return json.loads(obj_json)
        return None
    
    @cache_enabled
    async def delete_object(self, 
                            key
                            )-> None:
        '''Delete an object from the cache'''
        
        if self.client:
            try:
                await self.client.delete(key)
            except Exception as e:
                logger.error(f"Failed to delete object from Redis {e}")   
        else:
            self.local_cache.pop(key, None)


cache = RCache()
        
# Example usage to set and get an object:
# await cache.set_object('my_key', {'name': 'John', 'age': 30}, expire=3600)
# obj = await cache.get_object('my_key')
# print(obj)

# Example usage to delete an object:
# await cache.delete_object('my_key')