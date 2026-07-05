"""
SQLite数据存储模块

提供K线数据的本地缓存存储，避免重复从MT5拉取历史数据。
"""
import sqlite3
from typing import Optional
from datetime import datetime
import pandas as pd
from pathlib import Path


class DataStore:
    """
    SQLite数据存储类

    用于存储和管理K线历史数据。
    支持按品种、时间周期存储和查询。
    """

    def __init__(self, db_path: str = "quant.db"):
        """
        初始化数据存储

        Args:
            db_path: 数据库文件路径
        """
        self.db_path = db_path
        self._ensure_database()
        self.create_table()

    def _ensure_database(self):
        """
        确保数据库目录存在
        """
        db_file = Path(self.db_path)
        if db_file.is_absolute():
            db_file.parent.mkdir(parents=True, exist_ok=True)
        else:
            # 相对路径，创建当前目录
            Path.cwd().mkdir(parents=True, exist_ok=True)

    def _get_connection(self) -> sqlite3.Connection:
        """
        获取数据库连接

        Returns:
            sqlite3.Connection
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def create_table(self):
        """
        创建K线数据表

        表结构:
            - symbol: 品种代码
            - timeframe: 时间周期
            - time: K线时间
            - open: 开盘价
            - high: 最高价
            - low: 最低价
            - close: 收盘价
            - tick_volume: 成交量
            - spread: 点差

        主键: (symbol, timeframe, time)
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS rates (
                symbol TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                time INTEGER NOT NULL,
                open REAL NOT NULL,
                high REAL NOT NULL,
                low REAL NOT NULL,
                close REAL NOT NULL,
                tick_volume REAL NOT NULL,
                spread REAL NOT NULL,
                PRIMARY KEY (symbol, timeframe, time)
            )
        """)

        # 创建索引以加速查询
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_symbol_time
            ON rates (symbol, timeframe, time)
        """)

        conn.commit()
        conn.close()

    def save_rates(
        self,
        symbol: str,
        timeframe: str,
        df: pd.DataFrame
    ) -> int:
        """
        保存K线数据到数据库

        使用 INSERT OR REPLACE 策略，如果数据已存在则更新。

        Args:
            symbol: 品种代码
            timeframe: 时间周期
            df: K线数据DataFrame，必须包含列: time, open, high, low, close, tick_volume, spread

        Returns:
            int: 插入/更新的记录数
        """
        if df.empty:
            return 0

        # 验证必要列存在
        required_cols = {'time', 'open', 'high', 'low', 'close', 'tick_volume', 'spread'}
        missing = required_cols - set(df.columns)
        if missing:
            raise ValueError(f"DataFrame缺少必要列: {missing}")

        conn = self._get_connection()
        cursor = conn.cursor()

        # 准备插入数据
        insert_sql = """
            INSERT OR REPLACE INTO rates
            (symbol, timeframe, time, open, high, low, close, tick_volume, spread)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """

        records = []
        for _, row in df.iterrows():
            # 转换时间为时间戳
            if isinstance(row['time'], datetime):
                timestamp = int(row['time'].timestamp())
            elif isinstance(row['time'], pd.Timestamp):
                timestamp = int(row['time'].timestamp())
            else:
                timestamp = int(row['time'])

            records.append((
                symbol,
                timeframe,
                timestamp,
                float(row['open']),
                float(row['high']),
                float(row['low']),
                float(row['close']),
                float(row['tick_volume']),
                float(row['spread'])
            ))

        cursor.executemany(insert_sql, records)
        affected = cursor.rowcount

        conn.commit()
        conn.close()

        return affected

    def load_rates(
        self,
        symbol: str,
        timeframe: str,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None
    ) -> pd.DataFrame:
        """
        从数据库加载K线数据

        Args:
            symbol: 品种代码
            timeframe: 时间周期
            start: 开始时间（可选）
            end: 结束时间（可选）

        Returns:
            pandas.DataFrame，包含列: time, open, high, low, close, tick_volume, spread
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # 构建查询
        query = """
            SELECT time, open, high, low, close, tick_volume, spread
            FROM rates
            WHERE symbol = ? AND timeframe = ?
        """
        params = [symbol, timeframe]

        if start is not None:
            start_ts = int(start.timestamp())
            query += " AND time >= ?"
            params.append(start_ts)

        if end is not None:
            end_ts = int(end.timestamp())
            query += " AND time <= ?"
            params.append(end_ts)

        query += " ORDER BY time ASC"

        cursor.execute(query, params)
        rows = cursor.fetchall()

        conn.close()

        if not rows:
            return pd.DataFrame()

        # 转换为DataFrame
        df = pd.DataFrame([dict(row) for row in rows])

        # 转换时间列为datetime
        df['time'] = pd.to_datetime(df['time'], unit='s')

        return df

    def get_latest_time(
        self,
        symbol: str,
        timeframe: str
    ) -> Optional[datetime]:
        """
        获取数据库中某品种某周期的最新K线时间

        Args:
            symbol: 品种代码
            timeframe: 时间周期

        Returns:
            最新K线时间，如果没有数据则返回None
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT MAX(time) as latest_time
            FROM rates
            WHERE symbol = ? AND timeframe = ?
        """, [symbol, timeframe])

        result = cursor.fetchone()
        conn.close()

        if result and result['latest_time']:
            return datetime.fromtimestamp(result['latest_time'])

        return None

    def delete_rates(
        self,
        symbol: str,
        timeframe: str,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None
    ) -> int:
        """
        删除指定范围的K线数据

        Args:
            symbol: 品种代码
            timeframe: 时间周期
            start: 开始时间（可选）
            end: 结束时间（可选）

        Returns:
            删除的记录数
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        query = """
            DELETE FROM rates
            WHERE symbol = ? AND timeframe = ?
        """
        params = [symbol, timeframe]

        if start is not None:
            start_ts = int(start.timestamp())
            query += " AND time >= ?"
            params.append(start_ts)

        if end is not None:
            end_ts = int(end.timestamp())
            query += " AND time <= ?"
            params.append(end_ts)

        cursor.execute(query, params)
        affected = cursor.rowcount

        conn.commit()
        conn.close()

        return affected

    def get_available_symbols(self) -> list:
        """
        获取数据库中所有已存储的品种

        Returns:
            品种代码列表
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT DISTINCT symbol
            FROM rates
            ORDER BY symbol
        """)

        symbols = [row['symbol'] for row in cursor.fetchall()]
        conn.close()

        return symbols

    def get_statistics(self) -> dict:
        """
        获取数据库统计信息

        Returns:
            dict，包含各品种各周期的记录数
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT symbol, timeframe, COUNT(*) as count,
                   MIN(time) as earliest,
                   MAX(time) as latest
            FROM rates
            GROUP BY symbol, timeframe
            ORDER BY symbol, timeframe
        """)

        stats = []
        for row in cursor.fetchall():
            stats.append({
                'symbol': row['symbol'],
                'timeframe': row['timeframe'],
                'count': row['count'],
                'earliest': datetime.fromtimestamp(row['earliest']).isoformat() if row['earliest'] else None,
                'latest': datetime.fromtimestamp(row['latest']).isoformat() if row['latest'] else None,
            })

        conn.close()

        return {'data': stats}
