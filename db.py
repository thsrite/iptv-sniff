"""
Database abstraction layer for IPTV Sniffer
Supports SQLite, PostgreSQL, and JSON file storage
"""
import json
import os
import sqlite3
from typing import Dict, List, Any, Optional


class Database:
    """Abstract database interface"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.db_type = config.get('database', {}).get('type', 'json')

        if self.db_type == 'sqlite':
            self.db = SQLiteDatabase(config)
        elif self.db_type == 'postgresql':
            self.db = PostgreSQLDatabase(config)
        else:
            self.db = JSONDatabase(config)

    def __getattr__(self, name):
        return getattr(self.db, name)


class JSONDatabase:
    """JSON file-based storage (original implementation)"""

    def __init__(self, config: Dict[str, Any]):
        self.channels_file = 'tv_channels.json'
        self.groups_file = 'tv_groups.json'
        self.results_file = 'results.json'

    # Channels
    def get_all_channels(self) -> Dict[str, Any]:
        if os.path.exists(self.channels_file):
            with open(self.channels_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}

    def save_channels(self, channels: Dict[str, Any]):
        with open(self.channels_file, 'w', encoding='utf-8') as f:
            json.dump(channels, f, ensure_ascii=False, indent=2)

    def get_channel(self, ip: str) -> Optional[Dict[str, Any]]:
        channels = self.get_all_channels()
        return channels.get(ip)

    def update_channel(self, ip: str, data: Dict[str, Any]):
        channels = self.get_all_channels()
        if ip not in channels:
            channels[ip] = {}
        channels[ip].update(data)
        self.save_channels(channels)

    def delete_channel(self, ip: str):
        channels = self.get_all_channels()
        if ip in channels:
            del channels[ip]
            self.save_channels(channels)

    # Groups
    def get_all_groups(self) -> Dict[str, Any]:
        if os.path.exists(self.groups_file):
            with open(self.groups_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}

    def save_groups(self, groups: Dict[str, Any]):
        with open(self.groups_file, 'w', encoding='utf-8') as f:
            json.dump(groups, f, ensure_ascii=False, indent=2)

    def get_group(self, group_id: str) -> Optional[Dict[str, Any]]:
        groups = self.get_all_groups()
        return groups.get(group_id)

    def update_group(self, group_id: str, data: Dict[str, Any]):
        groups = self.get_all_groups()
        if group_id not in groups:
            groups[group_id] = {}
        groups[group_id].update(data)
        self.save_groups(groups)

    def delete_group(self, group_id: str):
        groups = self.get_all_groups()
        if group_id in groups:
            del groups[group_id]
            self.save_groups(groups)

    # Test Results
    def get_all_results(self) -> Dict[str, Any]:
        if os.path.exists(self.results_file):
            with open(self.results_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}

    def save_results(self, results: Dict[str, Any]):
        with open(self.results_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

    def get_result(self, test_id: str) -> Optional[Dict[str, Any]]:
        results = self.get_all_results()
        return results.get(test_id)

    def update_result(self, test_id: str, data: Dict[str, Any]):
        results = self.get_all_results()
        results[test_id] = data
        self.save_results(results)

    def delete_result(self, test_id: str):
        results = self.get_all_results()
        if test_id in results:
            del results[test_id]
            self.save_results(results)


class SQLiteDatabase:
    """SQLite database storage"""

    def __init__(self, config: Dict[str, Any]):
        db_config = config.get('database', {})
        self.db_path = db_config.get('sqlite_path', 'config/iptv.db')

        # Create config directory if not exists
        os.makedirs(os.path.dirname(self.db_path) if os.path.dirname(self.db_path) else '.', exist_ok=True)

        self._init_database()

    def _init_database(self):
        """Initialize database schema"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Create tables
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS channels (
                ip TEXT PRIMARY KEY,
                name TEXT DEFAULT '',
                logo TEXT DEFAULT '',
                tvg_id TEXT DEFAULT '',
                url TEXT DEFAULT '',
                screenshot TEXT DEFAULT '',
                resolution TEXT DEFAULT '',
                test_status TEXT DEFAULT 'success',
                playback TEXT DEFAULT '',
                catchup TEXT DEFAULT '',
                connectivity TEXT DEFAULT 'untested',
                timestamp TEXT DEFAULT ''
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS groups (
                id TEXT PRIMARY KEY,
                name TEXT,
                sort_order INTEGER
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS channel_groups (
                channel_ip TEXT,
                group_id TEXT,
                PRIMARY KEY (channel_ip, group_id),
                FOREIGN KEY (channel_ip) REFERENCES channels(ip) ON DELETE CASCADE,
                FOREIGN KEY (group_id) REFERENCES groups(id) ON DELETE CASCADE
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS test_results (
                test_id TEXT PRIMARY KEY,
                base_url TEXT,
                start_ip TEXT,
                end_ip TEXT,
                status TEXT,
                start_time TEXT,
                end_time TEXT,
                results TEXT
            )
        ''')

        # Create indexes
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_channels_test_status ON channels(test_status)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_channels_resolution ON channels(resolution)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_groups_sort_order ON groups(sort_order)')

        conn.commit()
        conn.close()

    def _get_connection(self):
        return sqlite3.connect(self.db_path)

    # Channels
    def get_all_channels(self) -> Dict[str, Any]:
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM channels')
        rows = cursor.fetchall()

        channels = {}
        for row in rows:
            ip = row[0]
            channels[ip] = {
                'name': row[1] or '',
                'logo': row[2] or '',
                'tvg_id': row[3] or '',
                'url': row[4] or '',
                'screenshot': row[5] or '',
                'resolution': row[6] or '',
                'test_status': row[7] or '',
                'playback': row[8] or '',
                'catchup': row[9] or '',
                'connectivity': row[10] or 'untested',
                'timestamp': row[11] or ''
            }

            # Get channel groups
            cursor.execute('''
                SELECT g.id, g.name FROM groups g
                JOIN channel_groups cg ON g.id = cg.group_id
                WHERE cg.channel_ip = ?
            ''', (ip,))
            groups = cursor.fetchall()
            channels[ip]['groups'] = [{'id': g[0], 'name': g[1]} for g in groups]

        conn.close()
        return channels

    def save_channels(self, channels: Dict[str, Any]):
        conn = self._get_connection()
        cursor = conn.cursor()

        # Use UPSERT to avoid deleting channel_groups relationships
        # Only update/insert channels, don't touch channel_groups table
        for ip, channel in channels.items():
            cursor.execute('''
                INSERT INTO channels
                (ip, name, logo, tvg_id, url, screenshot, resolution, test_status, playback, catchup, connectivity, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(ip) DO UPDATE SET
                    name = excluded.name,
                    logo = excluded.logo,
                    tvg_id = excluded.tvg_id,
                    url = excluded.url,
                    screenshot = excluded.screenshot,
                    resolution = excluded.resolution,
                    test_status = excluded.test_status,
                    playback = excluded.playback,
                    catchup = excluded.catchup,
                    connectivity = excluded.connectivity,
                    timestamp = excluded.timestamp
            ''', (
                ip,
                channel.get('name', ''),
                channel.get('logo', ''),
                channel.get('tvg_id', ''),
                channel.get('url', ''),
                channel.get('screenshot', ''),
                channel.get('resolution', ''),
                channel.get('test_status', ''),
                channel.get('playback', ''),
                channel.get('catchup', ''),
                channel.get('connectivity', 'untested'),
                channel.get('timestamp', '')
            ))

        conn.commit()
        conn.close()

    def get_channel(self, ip: str) -> Optional[Dict[str, Any]]:
        channels = self.get_all_channels()
        return channels.get(ip)

    def update_channel(self, ip: str, data: Dict[str, Any]):
        conn = self._get_connection()
        cursor = conn.cursor()

        # Check if channel exists
        cursor.execute('SELECT ip FROM channels WHERE ip = ?', (ip,))
        exists = cursor.fetchone()

        if exists:
            # Build update query dynamically based on provided fields
            fields = []
            values = []
            for key in ['name', 'logo', 'tvg_id', 'url', 'screenshot', 'resolution', 'test_status', 'playback', 'catchup', 'connectivity', 'timestamp']:
                if key in data:
                    fields.append(f"{key} = ?")
                    values.append(data[key])

            if fields:
                values.append(ip)
                query = f"UPDATE channels SET {', '.join(fields)} WHERE ip = ?"
                cursor.execute(query, values)
        else:
            # Insert new channel
            cursor.execute('''
                INSERT INTO channels
                (ip, name, logo, tvg_id, url, screenshot, resolution, test_status, playback, catchup, connectivity, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                ip,
                data.get('name', ''),
                data.get('logo', ''),
                data.get('tvg_id', ''),
                data.get('url', ''),
                data.get('screenshot', ''),
                data.get('resolution', ''),
                data.get('test_status', ''),
                data.get('playback', ''),
                data.get('catchup', ''),
                data.get('connectivity', 'untested'),
                data.get('timestamp', '')
            ))

        conn.commit()
        conn.close()

    def delete_channel(self, ip: str):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM channels WHERE ip = ?', (ip,))
        conn.commit()
        conn.close()

    # Groups
    def get_all_groups(self) -> Dict[str, Any]:
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM groups ORDER BY sort_order')
        rows = cursor.fetchall()

        groups = {}
        for row in rows:
            group_id = row[0]
            groups[group_id] = {
                'name': row[1],
                'sort_order': row[2],
                'channels': []
            }

            # Get channel IPs in this group
            cursor.execute('SELECT channel_ip FROM channel_groups WHERE group_id = ?', (group_id,))
            channel_ips = [r[0] for r in cursor.fetchall()]
            groups[group_id]['channels'] = channel_ips

        conn.close()
        return groups

    def save_groups(self, groups: Dict[str, Any]):
        conn = self._get_connection()
        cursor = conn.cursor()

        # Clear existing data
        cursor.execute('DELETE FROM channel_groups')
        cursor.execute('DELETE FROM groups')

        # Insert groups
        for group_id, group in groups.items():
            cursor.execute('''
                INSERT INTO groups (id, name, sort_order)
                VALUES (?, ?, ?)
            ''', (
                group_id,
                group.get('name', ''),
                group.get('sort_order', 9999)
            ))

            # Insert channel-group relationships
            for channel_ip in group.get('channels', []):
                cursor.execute('''
                    INSERT INTO channel_groups (channel_ip, group_id)
                    VALUES (?, ?)
                ''', (channel_ip, group_id))

        conn.commit()
        conn.close()

    def get_group(self, group_id: str) -> Optional[Dict[str, Any]]:
        groups = self.get_all_groups()
        return groups.get(group_id)

    def update_group(self, group_id: str, data: Dict[str, Any]):
        conn = self._get_connection()
        cursor = conn.cursor()

        # Check if group exists
        cursor.execute('SELECT id FROM groups WHERE id = ?', (group_id,))
        exists = cursor.fetchone()

        if exists:
            # Update group
            if 'name' in data or 'sort_order' in data:
                fields = []
                values = []
                if 'name' in data:
                    fields.append('name = ?')
                    values.append(data['name'])
                if 'sort_order' in data:
                    fields.append('sort_order = ?')
                    values.append(data['sort_order'])

                values.append(group_id)
                query = f"UPDATE groups SET {', '.join(fields)} WHERE id = ?"
                cursor.execute(query, values)

            # Update channels if provided
            if 'channels' in data:
                cursor.execute('DELETE FROM channel_groups WHERE group_id = ?', (group_id,))
                for channel_ip in data['channels']:
                    cursor.execute('''
                        INSERT INTO channel_groups (channel_ip, group_id)
                        VALUES (?, ?)
                    ''', (channel_ip, group_id))
        else:
            # Insert new group
            cursor.execute('''
                INSERT INTO groups (id, name, sort_order)
                VALUES (?, ?, ?)
            ''', (
                group_id,
                data.get('name', ''),
                data.get('sort_order', 9999)
            ))

            # Insert channels
            for channel_ip in data.get('channels', []):
                cursor.execute('''
                    INSERT INTO channel_groups (channel_ip, group_id)
                    VALUES (?, ?)
                ''', (channel_ip, group_id))

        conn.commit()
        conn.close()

    def delete_group(self, group_id: str):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM groups WHERE id = ?', (group_id,))
        conn.commit()
        conn.close()

    # Test Results
    def get_all_results(self) -> Dict[str, Any]:
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM test_results')
        rows = cursor.fetchall()

        results = {}
        for row in rows:
            test_id = row[0]
            results[test_id] = {
                'base_url': row[1],
                'start_ip': row[2],
                'end_ip': row[3],
                'status': row[4],
                'start_time': row[5],
                'end_time': row[6],
                'results': json.loads(row[7]) if row[7] else {}
            }

        conn.close()
        return results

    def save_results(self, results: Dict[str, Any]):
        conn = self._get_connection()
        cursor = conn.cursor()

        # Clear existing data
        cursor.execute('DELETE FROM test_results')

        # Insert results
        for test_id, result in results.items():
            cursor.execute('''
                INSERT INTO test_results
                (test_id, base_url, start_ip, end_ip, status, start_time, end_time, results)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                test_id,
                result.get('base_url', ''),
                result.get('start_ip', ''),
                result.get('end_ip', ''),
                result.get('status', ''),
                result.get('start_time', ''),
                result.get('end_time', ''),
                json.dumps(result.get('results', {}))
            ))

        conn.commit()
        conn.close()

    def get_result(self, test_id: str) -> Optional[Dict[str, Any]]:
        results = self.get_all_results()
        return results.get(test_id)

    def update_result(self, test_id: str, data: Dict[str, Any]):
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            INSERT OR REPLACE INTO test_results
            (test_id, base_url, start_ip, end_ip, status, start_time, end_time, results)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            test_id,
            data.get('base_url', ''),
            data.get('start_ip', ''),
            data.get('end_ip', ''),
            data.get('status', ''),
            data.get('start_time', ''),
            data.get('end_time', ''),
            json.dumps(data.get('results', {}))
        ))

        conn.commit()
        conn.close()

    def delete_result(self, test_id: str):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM test_results WHERE test_id = ?', (test_id,))
        conn.commit()
        conn.close()


class PostgreSQLDatabase:
    """PostgreSQL database storage"""

    def __init__(self, config: Dict[str, Any]):
        try:
            import psycopg2
            self.psycopg2 = psycopg2
        except ImportError:
            raise ImportError("psycopg2-binary is required for PostgreSQL support")

        db_config = config.get('database', {}).get('postgresql', {})
        self.host = db_config.get('host', 'localhost')
        self.port = db_config.get('port', 5432)
        self.database = db_config.get('database', 'iptv')
        self.user = db_config.get('user', 'postgres')
        self.password = db_config.get('password', '')

        self._init_database()

    def _init_database(self):
        """Initialize database schema"""
        conn = self._get_connection()
        cursor = conn.cursor()

        # Create tables (similar to SQLite but with PostgreSQL syntax)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS channels (
                ip TEXT PRIMARY KEY,
                name TEXT DEFAULT '',
                logo TEXT DEFAULT '',
                tvg_id TEXT DEFAULT '',
                url TEXT DEFAULT '',
                screenshot TEXT DEFAULT '',
                resolution TEXT DEFAULT '',
                test_status TEXT DEFAULT 'success',
                playback TEXT DEFAULT '',
                catchup TEXT DEFAULT '',
                connectivity TEXT DEFAULT 'untested',
                timestamp TEXT DEFAULT ''
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS groups (
                id TEXT PRIMARY KEY,
                name TEXT,
                sort_order INTEGER
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS channel_groups (
                channel_ip TEXT,
                group_id TEXT,
                PRIMARY KEY (channel_ip, group_id),
                FOREIGN KEY (channel_ip) REFERENCES channels(ip) ON DELETE CASCADE,
                FOREIGN KEY (group_id) REFERENCES groups(id) ON DELETE CASCADE
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS test_results (
                test_id TEXT PRIMARY KEY,
                base_url TEXT,
                start_ip TEXT,
                end_ip TEXT,
                status TEXT,
                start_time TEXT,
                end_time TEXT,
                results TEXT
            )
        ''')

        # Create indexes
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_channels_test_status ON channels(test_status)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_channels_resolution ON channels(resolution)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_groups_sort_order ON groups(sort_order)')

        conn.commit()
        conn.close()

    def _get_connection(self):
        return self.psycopg2.connect(
            host=self.host,
            port=self.port,
            database=self.database,
            user=self.user,
            password=self.password
        )

    # The rest of the methods are similar to SQLiteDatabase
    # but use %s placeholders instead of ? and ON CONFLICT syntax for upserts

    def get_all_channels(self) -> Dict[str, Any]:
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM channels')
        rows = cursor.fetchall()

        channels = {}
        for row in rows:
            ip = row[0]
            channels[ip] = {
                'name': row[1] or '',
                'logo': row[2] or '',
                'tvg_id': row[3] or '',
                'url': row[4] or '',
                'screenshot': row[5] or '',
                'resolution': row[6] or '',
                'test_status': row[7] or '',
                'playback': row[8] or '',
                'catchup': row[9] or '',
                'connectivity': row[10] or 'untested',
                'timestamp': row[11] or ''
            }

            cursor.execute('''
                SELECT g.id, g.name FROM groups g
                JOIN channel_groups cg ON g.id = cg.group_id
                WHERE cg.channel_ip = %s
            ''', (ip,))
            groups = cursor.fetchall()
            channels[ip]['groups'] = [{'id': g[0], 'name': g[1]} for g in groups]

        conn.close()
        return channels

    def save_channels(self, channels: Dict[str, Any]):
        conn = self._get_connection()
        cursor = conn.cursor()

        # Use UPSERT to avoid deleting channel_groups relationships
        # Only update/insert channels, don't touch channel_groups table
        for ip, channel in channels.items():
            cursor.execute('''
                INSERT INTO channels
                (ip, name, logo, tvg_id, url, screenshot, resolution, test_status, playback, catchup, connectivity, timestamp)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT(ip) DO UPDATE SET
                    name = EXCLUDED.name,
                    logo = EXCLUDED.logo,
                    tvg_id = EXCLUDED.tvg_id,
                    url = EXCLUDED.url,
                    screenshot = EXCLUDED.screenshot,
                    resolution = EXCLUDED.resolution,
                    test_status = EXCLUDED.test_status,
                    playback = EXCLUDED.playback,
                    catchup = EXCLUDED.catchup,
                    connectivity = EXCLUDED.connectivity,
                    timestamp = EXCLUDED.timestamp
            ''', (
                ip,
                channel.get('name', ''),
                channel.get('logo', ''),
                channel.get('tvg_id', ''),
                channel.get('url', ''),
                channel.get('screenshot', ''),
                channel.get('resolution', ''),
                channel.get('test_status', ''),
                channel.get('playback', ''),
                channel.get('catchup', ''),
                channel.get('connectivity', 'untested'),
                channel.get('timestamp', '')
            ))

        conn.commit()
        conn.close()

    def get_channel(self, ip: str) -> Optional[Dict[str, Any]]:
        channels = self.get_all_channels()
        return channels.get(ip)

    def update_channel(self, ip: str, data: Dict[str, Any]):
        conn = self._get_connection()
        cursor = conn.cursor()

        # Check if channel exists
        cursor.execute('SELECT ip FROM channels WHERE ip = %s', (ip,))
        exists = cursor.fetchone()

        if exists:
            # Build update query dynamically based on provided fields
            fields = []
            values = []
            for key in ['name', 'logo', 'tvg_id', 'url', 'screenshot', 'resolution', 'test_status', 'playback', 'catchup', 'connectivity', 'timestamp']:
                if key in data:
                    fields.append(f"{key} = %s")
                    values.append(data[key])

            if fields:
                values.append(ip)
                query = f"UPDATE channels SET {', '.join(fields)} WHERE ip = %s"
                cursor.execute(query, values)
        else:
            # Insert new channel
            cursor.execute('''
                INSERT INTO channels
                (ip, name, logo, tvg_id, url, screenshot, resolution, test_status, playback, catchup, connectivity, timestamp)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ''', (
                ip,
                data.get('name', ''),
                data.get('logo', ''),
                data.get('tvg_id', ''),
                data.get('url', ''),
                data.get('screenshot', ''),
                data.get('resolution', ''),
                data.get('test_status', ''),
                data.get('playback', ''),
                data.get('catchup', ''),
                data.get('connectivity', 'untested'),
                data.get('timestamp', '')
            ))

        conn.commit()
        conn.close()

    def delete_channel(self, ip: str):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM channels WHERE ip = %s', (ip,))
        conn.commit()
        conn.close()

    # Groups
    def get_all_groups(self) -> Dict[str, Any]:
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM groups ORDER BY sort_order')
        rows = cursor.fetchall()

        groups = {}
        for row in rows:
            group_id = row[0]
            groups[group_id] = {
                'name': row[1],
                'sort_order': row[2],
                'channels': []
            }

            # Get channel IPs in this group
            cursor.execute('SELECT channel_ip FROM channel_groups WHERE group_id = %s', (group_id,))
            channel_ips = [r[0] for r in cursor.fetchall()]
            groups[group_id]['channels'] = channel_ips

        conn.close()
        return groups

    def save_groups(self, groups: Dict[str, Any]):
        conn = self._get_connection()
        cursor = conn.cursor()

        # Clear existing data
        cursor.execute('DELETE FROM channel_groups')
        cursor.execute('DELETE FROM groups')

        # Insert groups
        for group_id, group in groups.items():
            cursor.execute('''
                INSERT INTO groups (id, name, sort_order)
                VALUES (%s, %s, %s)
            ''', (
                group_id,
                group.get('name', ''),
                group.get('sort_order', 9999)
            ))

            # Insert channel-group relationships
            for channel_ip in group.get('channels', []):
                cursor.execute('''
                    INSERT INTO channel_groups (channel_ip, group_id)
                    VALUES (%s, %s)
                ''', (channel_ip, group_id))

        conn.commit()
        conn.close()

    def get_group(self, group_id: str) -> Optional[Dict[str, Any]]:
        groups = self.get_all_groups()
        return groups.get(group_id)

    def update_group(self, group_id: str, data: Dict[str, Any]):
        conn = self._get_connection()
        cursor = conn.cursor()

        # Check if group exists
        cursor.execute('SELECT id FROM groups WHERE id = %s', (group_id,))
        exists = cursor.fetchone()

        if exists:
            # Update group
            if 'name' in data or 'sort_order' in data:
                fields = []
                values = []
                if 'name' in data:
                    fields.append('name = %s')
                    values.append(data['name'])
                if 'sort_order' in data:
                    fields.append('sort_order = %s')
                    values.append(data['sort_order'])

                values.append(group_id)
                query = f"UPDATE groups SET {', '.join(fields)} WHERE id = %s"
                cursor.execute(query, values)

            # Update channels if provided
            if 'channels' in data:
                cursor.execute('DELETE FROM channel_groups WHERE group_id = %s', (group_id,))
                for channel_ip in data['channels']:
                    cursor.execute('''
                        INSERT INTO channel_groups (channel_ip, group_id)
                        VALUES (%s, %s)
                    ''', (channel_ip, group_id))
        else:
            # Insert new group
            cursor.execute('''
                INSERT INTO groups (id, name, sort_order)
                VALUES (%s, %s, %s)
            ''', (
                group_id,
                data.get('name', ''),
                data.get('sort_order', 9999)
            ))

            # Insert channels
            for channel_ip in data.get('channels', []):
                cursor.execute('''
                    INSERT INTO channel_groups (channel_ip, group_id)
                    VALUES (%s, %s)
                ''', (channel_ip, group_id))

        conn.commit()
        conn.close()

    def delete_group(self, group_id: str):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM groups WHERE id = %s', (group_id,))
        conn.commit()
        conn.close()

    # Test Results
    def get_all_results(self) -> Dict[str, Any]:
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM test_results')
        rows = cursor.fetchall()

        results = {}
        for row in rows:
            test_id = row[0]
            results[test_id] = {
                'base_url': row[1],
                'start_ip': row[2],
                'end_ip': row[3],
                'status': row[4],
                'start_time': row[5],
                'end_time': row[6],
                'results': json.loads(row[7]) if row[7] else {}
            }

        conn.close()
        return results

    def save_results(self, results: Dict[str, Any]):
        conn = self._get_connection()
        cursor = conn.cursor()

        # Clear existing data
        cursor.execute('DELETE FROM test_results')

        # Insert results
        for test_id, result in results.items():
            cursor.execute('''
                INSERT INTO test_results
                (test_id, base_url, start_ip, end_ip, status, start_time, end_time, results)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ''', (
                test_id,
                result.get('base_url', ''),
                result.get('start_ip', ''),
                result.get('end_ip', ''),
                result.get('status', ''),
                result.get('start_time', ''),
                result.get('end_time', ''),
                json.dumps(result.get('results', {}))
            ))

        conn.commit()
        conn.close()

    def get_result(self, test_id: str) -> Optional[Dict[str, Any]]:
        results = self.get_all_results()
        return results.get(test_id)

    def update_result(self, test_id: str, data: Dict[str, Any]):
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO test_results
            (test_id, base_url, start_ip, end_ip, status, start_time, end_time, results)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (test_id) DO UPDATE SET
                base_url = EXCLUDED.base_url,
                start_ip = EXCLUDED.start_ip,
                end_ip = EXCLUDED.end_ip,
                status = EXCLUDED.status,
                start_time = EXCLUDED.start_time,
                end_time = EXCLUDED.end_time,
                results = EXCLUDED.results
        ''', (
            test_id,
            data.get('base_url', ''),
            data.get('start_ip', ''),
            data.get('end_ip', ''),
            data.get('status', ''),
            data.get('start_time', ''),
            data.get('end_time', ''),
            json.dumps(data.get('results', {}))
        ))

        conn.commit()
        conn.close()

    def delete_result(self, test_id: str):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM test_results WHERE test_id = %s', (test_id,))
        conn.commit()
        conn.close()
