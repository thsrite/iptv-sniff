#!/usr/bin/env python3
"""
Migrate JSON data to SQLite or PostgreSQL database
"""
import json
import os
import sqlite3
import sys

def migrate_to_sqlite(db_path='config/iptv.db'):
    """Migrate JSON data to SQLite database"""

    # Create config directory if not exists
    os.makedirs(os.path.dirname(db_path) if os.path.dirname(db_path) else '.', exist_ok=True)

    # Connect to SQLite database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create tables
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS channels (
            ip TEXT PRIMARY KEY,
            name TEXT,
            logo TEXT,
            tvg_id TEXT,
            url TEXT,
            screenshot TEXT,
            resolution TEXT,
            test_status TEXT,
            playback TEXT,
            timestamp TEXT
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

    # Migrate tv_channels.json
    if os.path.exists('tv_channels.json'):
        print("Migrating tv_channels.json...")
        with open('tv_channels.json', 'r', encoding='utf-8') as f:
            channels = json.load(f)

        for ip, channel in channels.items():
            cursor.execute('''
                INSERT OR REPLACE INTO channels
                (ip, name, logo, tvg_id, url, screenshot, resolution, test_status, playback, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                channel.get('timestamp', '')
            ))

        print(f"Migrated {len(channels)} channels")

    # Migrate tv_groups.json
    if os.path.exists('tv_groups.json'):
        print("Migrating tv_groups.json...")
        with open('tv_groups.json', 'r', encoding='utf-8') as f:
            groups = json.load(f)

        for group_id, group in groups.items():
            cursor.execute('''
                INSERT OR REPLACE INTO groups (id, name, sort_order)
                VALUES (?, ?, ?)
            ''', (
                group_id,
                group.get('name', ''),
                group.get('sort_order', 9999)
            ))

            # Migrate channel-group relationships
            for channel_ip in group.get('channels', []):
                cursor.execute('''
                    INSERT OR REPLACE INTO channel_groups (channel_ip, group_id)
                    VALUES (?, ?)
                ''', (channel_ip, group_id))

        print(f"Migrated {len(groups)} groups")

    # Migrate results.json
    if os.path.exists('results.json'):
        print("Migrating results.json...")
        with open('results.json', 'r', encoding='utf-8') as f:
            results = json.load(f)

        for test_id, result in results.items():
            cursor.execute('''
                INSERT OR REPLACE INTO test_results
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

        print(f"Migrated {len(results)} test results")

    conn.commit()
    conn.close()

    print(f"\nMigration completed successfully!")
    print(f"Database created at: {db_path}")
    print("\nBackup your JSON files and update config to use SQLite database.")


def migrate_to_postgresql(host, port, database, user, password):
    """Migrate JSON data to PostgreSQL database"""
    try:
        import psycopg2
    except ImportError:
        print("Error: psycopg2 not installed. Install it with: pip install psycopg2-binary")
        sys.exit(1)

    # Connect to PostgreSQL
    conn = psycopg2.connect(
        host=host,
        port=port,
        database=database,
        user=user,
        password=password
    )
    cursor = conn.cursor()

    # Create tables
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS channels (
            ip TEXT PRIMARY KEY,
            name TEXT,
            logo TEXT,
            tvg_id TEXT,
            url TEXT,
            screenshot TEXT,
            resolution TEXT,
            test_status TEXT,
            playback TEXT,
            timestamp TEXT
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

    # Migrate tv_channels.json
    if os.path.exists('tv_channels.json'):
        print("Migrating tv_channels.json...")
        with open('tv_channels.json', 'r', encoding='utf-8') as f:
            channels = json.load(f)

        for ip, channel in channels.items():
            cursor.execute('''
                INSERT INTO channels
                (ip, name, logo, tvg_id, url, screenshot, resolution, test_status, playback, timestamp)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (ip) DO UPDATE SET
                    name = EXCLUDED.name,
                    logo = EXCLUDED.logo,
                    tvg_id = EXCLUDED.tvg_id,
                    url = EXCLUDED.url,
                    screenshot = EXCLUDED.screenshot,
                    resolution = EXCLUDED.resolution,
                    test_status = EXCLUDED.test_status,
                    playback = EXCLUDED.playback,
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
                channel.get('timestamp', '')
            ))

        print(f"Migrated {len(channels)} channels")

    # Migrate tv_groups.json
    if os.path.exists('tv_groups.json'):
        print("Migrating tv_groups.json...")
        with open('tv_groups.json', 'r', encoding='utf-8') as f:
            groups = json.load(f)

        for group_id, group in groups.items():
            cursor.execute('''
                INSERT INTO groups (id, name, sort_order)
                VALUES (%s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    name = EXCLUDED.name,
                    sort_order = EXCLUDED.sort_order
            ''', (
                group_id,
                group.get('name', ''),
                group.get('sort_order', 9999)
            ))

            # Migrate channel-group relationships
            for channel_ip in group.get('channels', []):
                cursor.execute('''
                    INSERT INTO channel_groups (channel_ip, group_id)
                    VALUES (%s, %s)
                    ON CONFLICT (channel_ip, group_id) DO NOTHING
                ''', (channel_ip, group_id))

        print(f"Migrated {len(groups)} groups")

    # Migrate results.json
    if os.path.exists('results.json'):
        print("Migrating results.json...")
        with open('results.json', 'r', encoding='utf-8') as f:
            results = json.load(f)

        for test_id, result in results.items():
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
                result.get('base_url', ''),
                result.get('start_ip', ''),
                result.get('end_ip', ''),
                result.get('status', ''),
                result.get('start_time', ''),
                result.get('end_time', ''),
                json.dumps(result.get('results', {}))
            ))

        print(f"Migrated {len(results)} test results")

    conn.commit()
    conn.close()

    print(f"\nMigration completed successfully!")
    print(f"Database: {database} on {host}:{port}")
    print("\nBackup your JSON files and update config to use PostgreSQL database.")


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Migrate JSON data to SQLite or PostgreSQL')
    parser.add_argument('--type', choices=['sqlite', 'postgresql'], default='sqlite',
                        help='Database type (default: sqlite)')
    parser.add_argument('--db-path', default='config/iptv.db',
                        help='SQLite database path (default: config/iptv.db)')
    parser.add_argument('--host', default='localhost',
                        help='PostgreSQL host (default: localhost)')
    parser.add_argument('--port', type=int, default=5432,
                        help='PostgreSQL port (default: 5432)')
    parser.add_argument('--database', default='iptv',
                        help='PostgreSQL database name (default: iptv)')
    parser.add_argument('--user', default='postgres',
                        help='PostgreSQL user (default: postgres)')
    parser.add_argument('--password', default='',
                        help='PostgreSQL password')

    args = parser.parse_args()

    if args.type == 'sqlite':
        migrate_to_sqlite(args.db_path)
    else:
        if not args.password:
            import getpass
            args.password = getpass.getpass('PostgreSQL password: ')
        migrate_to_postgresql(args.host, args.port, args.database, args.user, args.password)
