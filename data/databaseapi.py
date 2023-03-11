import aiosqlite
from static.common import get_hours_from_secs

async def check_tables(tbls):
    l = []
    async with aiosqlite.connect('data/urnby.db') as db:
        query = "SELECT name FROM sqlite_master WHERE type='table';"
        async with db.execute(query) as cursor:
            rows = await cursor.fetchall()
            l = [_[0] for _ in rows]
    if set(tbls).issubset(set(l)):
        
        return []
    return set(tbls) - set(l)
        
async def init_database():
    async with aiosqlite.connect('data/urnby.db') as db:
        query = f"""CREATE TABLE IF NOT EXISTS "historical"(server, user, character, session, in_timestamp, out_timestamp, _DEBUG_user_name, _DEBUG_in, _DEBUG_out, _DEBUG_delta);"""
        await db.execute(query)
        await db.commit()
        query = f"""CREATE TABLE IF NOT EXISTS "session"(server, session, created_by, _DEBUG_started_by, _DEBUG_start, start_timestamp, ended_by, _DEBUG_ended_by, _DEBUG_end, end_timestamp, _DEBUG_delta, hash);"""
        await db.execute(query)
        await db.commit()
        query = f"""CREATE TABLE IF NOT EXISTS "session_history"(server,     session,  created_by, _DEBUG_started_by,   _DEBUG_start,  start_timestamp, ended_by, _DEBUG_ended_by,  _DEBUG_end, end_timestamp,      _DEBUG_delta);"""
        await db.execute(query)
        await db.commit()
        query = f"""CREATE TABLE IF NOT EXISTS "active"(server, user, character, session, in_timestamp, out_timestamp, _DEBUG_user_name, _DEBUG_in, _DEBUG_out, _DEBUG_delta);"""
        await db.execute(query)
        await db.commit()
        query = f"""CREATE TABLE IF NOT EXISTS "commands"(server, command_name, options, datetime, user, user_name, channel_name);"""
        await db.execute(query)
        await db.commit()
        query = f"""CREATE TABLE IF NOT EXISTS "tod"(server, mob, tod_timestamp, submitted_timestamp, submitted_by_id, _DEBUG_submitted_datetime, _DEBUG_submitted_by, _DEBUG_tod_datetime);"""
        await db.execute(query)
        await db.commit()
        query = f"""CREATE TABLE IF NOT EXISTS "reps"(server, user, name, in_timestamp, UNIQUE(server, user));"""
        await db.execute(query)
        await db.commit()

async def flush_wal():
    async with aiosqlite.connect('data/urnby.db') as db:
        try:
            query = f"""PRAGMA journal_mode = DELETE"""
            res = await db.execute(query)
            await db.commit()
            print(f"Database mode set to: {await res.fetchall()}", flush=True)
            query = f"""PRAGMA journal_mode = WAL"""
            res = await db.execute(query)
            await db.commit()
            print(f"Database mode set to: {await res.fetchall()}", flush=True)
        except aiosqlite.OperationalError as err:
            print(f"Failed flushing WAL, are there multiple connections to the database?", flush=True)
            return False
    return True

async def set_db_to_wal():
    async with aiosqlite.connect('data/urnby.db') as db:
            query = f"PRAGMA journal_mode=WAL"
            res = await db.execute(query)
            print(f"Database mode set to: {await res.fetchall()}",flush=True)
            await db.commit() 
            
    # ==============================================================================
    # Session (session or session_history tables)
    # ============================================================================== 
    
async def get_session(guild_id):
    res = {}
    async with aiosqlite.connect('data/urnby.db') as db:
        db.row_factory = aiosqlite.Row
        query = f"""SELECT rowid, * FROM session WHERE server = {guild_id}"""
        async with db.execute(query) as cursor:
            rows = await cursor.fetchall()
            if len(rows) < 1:
                return None
            elif len(rows) > 1:
                raise ValueError(f'Error, server {guild_id} has more then one active session {len(rows)}')
            res = dict(rows[0])
    return res
    
async def set_session(guild_id, session):
    lastrow = 0
    async with aiosqlite.connect('data/urnby.db') as db:
        db.row_factory = aiosqlite.Row
        # Only one session allowed per server
        query = f"""SELECT count(*) FROM session WHERE server = {guild_id}"""
        async with db.execute(query) as cursor:
            res = await cursor.fetchall()
            if dict(res[0])['count(*)'] != 0:
                return None
        # Session name must be unique
        query = f"""SELECT count(*) FROM session_history WHERE server = {guild_id} AND session = '{session['session']}'"""
        async with db.execute(query) as cursor:
            res = await cursor.fetchall()
            if dict(res[0])['count(*)'] != 0:
                return None
            
        query = f"""INSERT INTO session(server,      session,  created_by,  _DEBUG_started_by,  _DEBUG_start,  start_timestamp,  ended_by,  _DEBUG_ended_by,  _DEBUG_end,  end_timestamp,  _DEBUG_delta)
                                 VALUES({guild_id}, :session, :created_by, :_DEBUG_started_by, :_DEBUG_start, :start_timestamp, :ended_by, :_DEBUG_ended_by, :_DEBUG_end, :end_timestamp, :_DEBUG_delta)"""
        async with db.execute(query, session) as cursor:
            lastrow = cursor.lastrowid
        await db.commit()
    return lastrow

async def delete_session(guild_id):
    lastrow = 0
    async with aiosqlite.connect('data/urnby.db') as db:
        db.row_factory = aiosqlite.Row
        query = f"""SELECT count(*) FROM session WHERE server = {guild_id}"""
        async with db.execute(query) as cursor:
            res = await cursor.fetchall()
            if dict(res[0])['count(*)'] != 1:
                return None
        query = f"""DELETE FROM session WHERE server = {guild_id}"""
        async with db.execute(query) as cursor:
            lastrow = cursor.lastrowid
        await db.commit()
    return lastrow


async def store_historical_session(guild_id, session):
    lastrow = 0
    async with aiosqlite.connect('data/urnby.db') as db:
        query = f"""INSERT INTO session_history(server,      session,  created_by,  _DEBUG_started_by,  _DEBUG_start,  start_timestamp,  ended_by,  _DEBUG_ended_by,  _DEBUG_end,  end_timestamp,  _DEBUG_delta)
                                         VALUES({guild_id}, :session, :created_by, :_DEBUG_started_by, :_DEBUG_start, :start_timestamp, :ended_by, :_DEBUG_ended_by, :_DEBUG_end, :end_timestamp, :_DEBUG_delta)"""
        async with db.execute(query, session) as cursor:
            lastrow = cursor.lastrowid
        await db.commit()
    return lastrow

async def get_last_rows_historical_session(guild_id, count):
    res = []
    async with aiosqlite.connect('data/urnby.db') as db:
        db.row_factory = aiosqlite.Row
        query = f"""SELECT rowid, * FROM session_history WHERE server = {guild_id} ORDER BY rowid DESC LIMIT {count}"""
        async with db.execute(query) as cursor:
            rows = await cursor.fetchall()
            res = [dict(row) for row in rows]
    return res

    # ==============================================================================
    # Records (active or historical tables)
    # ==============================================================================
    
async def get_all_actives(guild_id) -> list:
    res = []
    async with aiosqlite.connect('data/urnby.db') as db:
        db.row_factory = aiosqlite.Row
        query = f"SELECT rowid, * FROM active WHERE server = {guild_id}"
        async with db.execute(query) as cursor:
            rows = await cursor.fetchall()
            res = [dict(row) for row in rows]
    return res

# Returns None on user was already in active
async def store_active_record(guild_id, record):
    guild_actives = await get_all_actives(str(guild_id))
    for item in guild_actives:
        if item['user'] == record['user']:
            return None
            
    lastrow = 0
    async with aiosqlite.connect('data/urnby.db') as db:
        query = f"""INSERT INTO active(server,      user,  character,  session,  in_timestamp,  out_timestamp,  _DEBUG_user_name,  _DEBUG_in,  _DEBUG_out,  _DEBUG_delta)
                                VALUES({guild_id}, :user, :character, :session, :in_timestamp, :out_timestamp, :_DEBUG_user_name, :_DEBUG_in, :_DEBUG_out, :_DEBUG_delta)"""
        async with db.execute(query, record) as cursor:
            lastrow = cursor.lastrowid
        await db.commit()
    return lastrow

# Returns None on user not in active
async def remove_active_record(guild_id, record):
    lastrow = 0
    async with aiosqlite.connect('data/urnby.db') as db:
        db.row_factory = aiosqlite.Row
        query = f"""SELECT count(*) FROM active WHERE server = {guild_id} AND user = {record['user']}"""
        async with db.execute(query) as cursor:
            res = await cursor.fetchall()
            if dict(res[0])['count(*)'] == 0:
                return None
        query = f"""DELETE FROM active WHERE server = {guild_id} AND user = {record['user']}"""
        async with db.execute(query) as cursor:
            lastrow = cursor.lastrowid
        await db.commit()
    return lastrow
    
async def get_historical(guild_id):
    res = []
    async with aiosqlite.connect('data/urnby.db') as db:
        db.row_factory = aiosqlite.Row
        query = f"SELECT rowid, * FROM historical WHERE server = {guild_id}"
        async with db.execute(query) as cursor:
            rows = await cursor.fetchall()
            res = [dict(row) for row in rows]
    return res
    
async def get_last_rows_historical(guild_id, count):
    res = []
    async with aiosqlite.connect('data/urnby.db') as db:
        db.row_factory = aiosqlite.Row
        query = f"""SELECT rowid, * FROM historical WHERE server = {guild_id} ORDER BY rowid DESC LIMIT {count}"""
        async with db.execute(query) as cursor:
            rows = await cursor.fetchall()
            res = [dict(row) for row in rows]
    return res

async def get_historical_user(guild_id, user_id):
    res = []
    async with aiosqlite.connect('data/urnby.db') as db:
        db.row_factory = aiosqlite.Row
        query = f"SELECT rowid, * FROM historical WHERE server = {guild_id} AND user = {user_id}"
        async with db.execute(query) as cursor:
            rows = await cursor.fetchall()
            res = [dict(row) for row in rows]
    return res
    
async def get_historical_record(guild_id, rowid):
    res = []
    async with aiosqlite.connect('data/urnby.db') as db:
        db.row_factory = aiosqlite.Row
        query = f"SELECT rowid, * FROM historical WHERE server = {guild_id} AND rowid = {rowid}"
        async with db.execute(query) as cursor:
            rows = await cursor.fetchall()
            res = [dict(row) for row in rows]
        await db.commit()
    return res
    
async def store_new_historical(guild_id, record):
    lastrow = 0
    async with aiosqlite.connect('data/urnby.db') as db:
        query = f"""INSERT INTO historical(server,      user,  character,  session,  in_timestamp,  out_timestamp,  _DEBUG_user_name,  _DEBUG_in,  _DEBUG_out,  _DEBUG_delta)
                                    VALUES({guild_id}, :user, :character, :session, :in_timestamp, :out_timestamp, :_DEBUG_user_name, :_DEBUG_in, :_DEBUG_out, :_DEBUG_delta)"""
        async with db.execute(query, record) as cursor:
            lastrow = cursor.lastrowid
        await db.commit()
    return lastrow

async def delete_historical_record(guild_id, rowid):
    res = []
    async with aiosqlite.connect('data/urnby.db') as db:
        query = f"DELETE FROM historical WHERE server = {guild_id} AND rowid = {rowid}"
        async with db.execute(query) as cursor:
            res = await cursor.fetchall()
        await db.commit()
    return res
    
    # ==============================================================================
    # Commands (commands table)
    # ============================================================================== 

async def store_command(guild_id, command):
    lastrow = 0
    async with aiosqlite.connect('data/urnby.db') as db:
        query = f"""INSERT INTO commands(server,      command_name,  options,  datetime,  user,  user_name,  channel_name)
                                  VALUES({guild_id}, :command_name, :options, :datetime, :user, :user_name, :channel_name)"""
        async with db.execute(query, command) as cursor:
            lastrow = cursor.lastrowid
        await db.commit()
    return lastrow
    
async def get_commands_history(guild_id):
    res = []
    async with aiosqlite.connect('data/urnby.db') as db:
        db.row_factory = aiosqlite.Row
        query = f"""SELECT rowid, * FROM commands WHERE server = {guild_id}"""
        async with db.execute(query) as cursor:
            rows = await cursor.fetchall()
            res = [dict(row) for row in rows]
    return res

async def get_last_rows_commands_history(guild_id, count) -> list[dict]:
    res = []
    async with aiosqlite.connect('data/urnby.db') as db:
        db.row_factory = aiosqlite.Row
        query = f"""SELECT rowid, * FROM commands WHERE server = {guild_id} ORDER BY rowid DESC LIMIT {count}"""
        async with db.execute(query) as cursor:
            rows = await cursor.fetchall()
            res = [dict(row) for row in rows]
    return res

async def get_user_commands_history(guild_id, user_id, start_at=None, count=10) -> list[dict]:
    res = []
    async with aiosqlite.connect('data/urnby.db') as db:
        db.row_factory = aiosqlite.Row
        if start_at:
            count += start_at
        query = f"""SELECT rowid, * FROM commands WHERE server = {guild_id} and user = {user_id} ORDER BY rowid DESC LIMIT {count}"""
        async with db.execute(query) as cursor:
            rows = await cursor.fetchall()
            res = [dict(row) for row in rows]
        if start_at:
            res = res[start_at:]
    return res
    # ==============================================================================
    # Tod
    # ============================================================================== 

async def get_tod(guild_id, mob_name="Drusella Sathir") -> dict:
    res = []
    async with aiosqlite.connect('data/urnby.db') as db:
        db.row_factory = aiosqlite.Row
        query = f"SELECT rowid, * FROM tod WHERE server = {guild_id} ORDER BY submitted_timestamp DESC LIMIT 1"
        async with db.execute(query) as cursor:
            row = await cursor.fetchone()
            if not row:
                return None
            res = dict(row)
    return res
    
async def store_tod(guild_id, info):
    lastrow = 0
    async with aiosqlite.connect('data/urnby.db') as db:
        query = f"""INSERT INTO tod(server,       mob,  tod_timestamp,  submitted_timestamp,  submitted_by_id,  _DEBUG_submitted_datetime,  _DEBUG_submitted_by,  _DEBUG_tod_datetime)
                             VALUES({guild_id}, :mob, :tod_timestamp, :submitted_timestamp, :submitted_by_id, :_DEBUG_submitted_datetime, :_DEBUG_submitted_by, :_DEBUG_tod_datetime)"""
        async with db.execute(query, info) as cursor:
            lastrow = cursor.lastrowid
        await db.commit()
    return lastrow
    
    # ==============================================================================
    # Replacement Queue
    # ============================================================================== 

async def get_replacement_queue(guild_id) -> list:
    res = []
    async with aiosqlite.connect('data/urnby.db') as db:
        db.row_factory = aiosqlite.Row
        query = f"SELECT rowid, * FROM reps WHERE server = {guild_id} ORDER BY in_timestamp"
        async with db.execute(query) as cursor:
            rows = await cursor.fetchall()
            res = [dict(row) for row in rows]
    return res

async def add_replacement(guild_id, replacement):
    lastrow = 0
    async with aiosqlite.connect('data/urnby.db') as db:
        try:
            query = f"""INSERT INTO reps(server,      user, in_timestamp)
                                    VALUES({guild_id}, :user, :in_timestamp)"""
            async with db.execute(query, replacement) as cursor:
                lastrow = cursor.lastrowid
        except aiosqlite.IntegrityError:
            return None
        else:
            await db.commit()
    return lastrow

async def remove_replacement(guild_id, user_id):
    lastrow = 0
    async with aiosqlite.connect('data/urnby.db') as db:
        db.row_factory = aiosqlite.Row
        query = f"""SELECT count(*) FROM reps WHERE server = {guild_id} AND user = {user_id}"""
        async with db.execute(query) as cursor:
            res = await cursor.fetchall()
            if dict(res[0])['count(*)'] == 0:
                return None
        query = f"""DELETE FROM reps WHERE server = {guild_id} AND user = {user_id}"""
        async with db.execute(query) as cursor:
            lastrow = cursor.lastrowid
        await db.commit()
    return lastrow

async def clear_replacement_queue(guild_id):
    lastrow = 0
    async with aiosqlite.connect('data/urnby.db') as db:
        db.row_factory = aiosqlite.Row
        query = f"""DELETE FROM reps"""
        async with db.execute(query) as cursor:
            lastrow = cursor.lastrowid
        await db.commit()
    return lastrow

    # ==============================================================================
    # Misc
    # ============================================================================== 
    
# Returns list of int of unique users stored in historical for a given guild
async def get_unique_users(guild_id) -> list[int]:
    res = []
    async with aiosqlite.connect('data/urnby.db') as db:
        db.row_factory = aiosqlite.Row
        query = f"SELECT DISTINCT user FROM historical WHERE server = {guild_id}"
        async with db.execute(query) as cursor:
            rows = await cursor.fetchall()
            res = [row['user'] for row in rows]
    return res

async def get_user_seconds(guild_id, user, guild_historical=None):
    
    if not guild_historical:
        guild_historical = await get_historical(guild_id)
    
    if not guild_historical:
        return None
        
    found = [_ for _ in guild_historical if _['user'] == int(user)]
    
    if len(found) == 0:
        return 0
    
    in_tot = 0
    out_tot = 0
    for item in found:
        in_tot += item['in_timestamp']
        out_tot += item['out_timestamp']
    return out_tot - in_tot

async def get_user_hours(guild_id, user, guild_historical=None) -> float:
    secs = await get_user_seconds(guild_id, user, guild_historical)
    return get_hours_from_secs(secs)

# Wraps get_users_hours but only needs one grab from historical json
async def get_users_hours(guild_id, users) -> list[dict]:
    guild_historical = await get_historical(guild_id)
    res = []
    if not guild_historical:
        return res
    
    for user in users:
        tot = await get_user_hours(guild_id, user, guild_historical)
        res.append({'user': user, 'total':tot})
    return res