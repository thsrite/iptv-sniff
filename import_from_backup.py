#!/usr/bin/env python3
"""
Import data from backup directory to PostgreSQL
"""
import json
import os
import sys

def import_to_postgresql(host, port, database, user, password):
    """Import data from backup directory to PostgreSQL"""
    try:
        import psycopg2
    except ImportError:
        print("Error: psycopg2 not installed. Install it with: pip install psycopg2-binary")
        sys.exit(1)

    # Define file paths
    backup_dir = 'backup'
    channels_file = os.path.join(backup_dir, 'channels.json')
    groups_file = os.path.join(backup_dir, 'groups.json')
    results_file = os.path.join(backup_dir, 'results.json')

    # Connect to PostgreSQL
    print(f"Connecting to PostgreSQL database: {database} on {host}:{port}")
    conn = psycopg2.connect(
        host=host,
        port=port,
        database=database,
        user=user,
        password=password
    )
    cursor = conn.cursor()

    # Create tables if not exist
    print("Creating tables...")
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

    # Import channels
    if os.path.exists(channels_file):
        print(f"\nImporting channels from {channels_file}...")
        with open(channels_file, 'r', encoding='utf-8') as f:
            channels = json.load(f)

        for ip, channel in channels.items():
            cursor.execute('''
                INSERT INTO channels
                (ip, name, logo, tvg_id, url, screenshot, resolution, test_status, playback, catchup, connectivity, timestamp)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (ip) DO UPDATE SET
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

        print(f"✓ Imported {len(channels)} channels")
    else:
        print(f"⚠ File not found: {channels_file}")

    # Import groups
    if os.path.exists(groups_file):
        print(f"\nImporting groups from {groups_file}...")
        with open(groups_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            groups = data.get('groups', {})

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

            # Import channel-group relationships
            for channel_ip in group.get('channels', []):
                cursor.execute('''
                    INSERT INTO channel_groups (channel_ip, group_id)
                    VALUES (%s, %s)
                    ON CONFLICT (channel_ip, group_id) DO NOTHING
                ''', (channel_ip, group_id))

        print(f"✓ Imported {len(groups)} groups")
    else:
        print(f"⚠ File not found: {groups_file}")

    # Import test results
    if os.path.exists(results_file):
        print(f"\nImporting test results from {results_file}...")
        with open(results_file, 'r', encoding='utf-8') as f:
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

        print(f"✓ Imported {len(results)} test results")
    else:
        print(f"⚠ File not found: {results_file}")

    conn.commit()
    conn.close()

    print(f"\n{'='*60}")
    print("Import completed successfully!")
    print(f"{'='*60}")
    print(f"Database: {database} on {host}:{port}")
    print("\nNext steps:")
    print("1. Open Advanced Settings in the application")
    print("2. Select 'PostgreSQL' as database type")
    print("3. Enter database connection details")
    print("4. Save configuration and restart the application")


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Import backup data to PostgreSQL')
    parser.add_argument('--host', default='localhost', help='PostgreSQL host (default: localhost)')
    parser.add_argument('--port', type=int, default=5432, help='PostgreSQL port (default: 5432)')
    parser.add_argument('--database', default='iptv', help='PostgreSQL database name (default: iptv)')
    parser.add_argument('--user', default='postgres', help='PostgreSQL user (default: postgres)')
    parser.add_argument('--password', default='', help='PostgreSQL password')

    args = parser.parse_args()

    if not args.password:
        import getpass
        args.password = getpass.getpass('PostgreSQL password: ')

    import_to_postgresql(args.host, args.port, args.database, args.user, args.password)
