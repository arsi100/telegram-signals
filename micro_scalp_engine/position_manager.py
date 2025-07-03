class DynamicPositionManager:
    def __init__(self, initial_capital=10000, leverage=10):
        self.initial_capital = initial_capital
        self.leverage = leverage
        self.positions = {}
        self.min_profit_target = 0.004  # 0.4%
        
    def evaluate_exit(self, position_id: str, current_data: Dict) -> Tuple[bool, str]:
        """Evaluate whether to exit a position using dynamic criteria."""
        position = self.positions[position_id]
        entry_price = position['entry_price']
        current_price = current_data['1m']['close'].iloc[-1]
        
        # Calculate current P&L
        pnl_pct = (current_price - entry_price) / entry_price
        if position['side'] == 'SHORT':
            pnl_pct = -pnl_pct
            
        # Get multi-timeframe data
        m1_data = current_data['1m']
        m5_data = current_data['5m']
        h1_data = current_data['1h']
        
        # 1. Check if minimum profit target hit with strong momentum
        if pnl_pct >= self.min_profit_target:
            # Check if momentum is still strong
            m5_momentum = self.calculate_momentum(m5_data)
            if m5_momentum * (1 if position['side'] == 'LONG' else -1) < 0:
                return True, "Exit: Minimum profit target hit with momentum reversal"
                
        # 2. Dynamic trailing stop based on volatility
        atr = self.calculate_atr(m5_data)
        trailing_distance = max(0.003, min(0.01, atr * 0.5))  # 0.3% to 1% based on volatility
        
        if position.get('max_profit', 0) < pnl_pct:
            position['max_profit'] = pnl_pct
        elif position['max_profit'] - pnl_pct > trailing_distance:
            return True, f"Exit: Trailing stop hit ({trailing_distance*100:.1f}% from high)"
            
        # 3. Check for strong reversal signals
        if self.detect_reversal(m1_data, m5_data, h1_data, position['side']):
            return True, "Exit: Strong reversal detected"
            
        # 4. Time-based exit if no progress
        time_in_trade = current_data['1m'].index[-1] - position['entry_time']
        if time_in_trade.total_seconds() > 3600:  # 1 hour
            if pnl_pct < self.min_profit_target:
                return True, "Exit: No significant progress after 1 hour"
                
        return False, ""
        
    def calculate_momentum(self, df: pd.DataFrame) -> float:
        """Calculate momentum score."""
        # MACD
        exp1 = df['close'].ewm(span=12, adjust=False).mean()
        exp2 = df['close'].ewm(span=26, adjust=False).mean()
        macd = exp1 - exp2
        signal = macd.ewm(span=9, adjust=False).mean()
        hist = macd - signal
        
        # RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        # Combine signals
        momentum_score = (
            0.5 * np.sign(hist.iloc[-1]) +
            0.3 * (1 if rsi.iloc[-1] > 50 else -1) +
            0.2 * np.sign(df['close'].diff().iloc[-1])
        )
        
        return momentum_score
        
    def calculate_atr(self, df: pd.DataFrame, period=14) -> float:
        """Calculate Average True Range."""
        high = df['high']
        low = df['low']
        close = df['close']
        
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(period).mean()
        
        return atr.iloc[-1]
        
    def detect_reversal(self, m1_data: pd.DataFrame, m5_data: pd.DataFrame, 
                       h1_data: pd.DataFrame, position_side: str) -> bool:
        """Detect potential reversal signals."""
        # 1. Price action (engulfing patterns, long wicks)
        m5_candles = m5_data.tail(3)
        body_sizes = abs(m5_candles['close'] - m5_candles['open'])
        wick_sizes = m5_candles['high'] - m5_candles['low']
        
        # Long wick against position
        if position_side == 'LONG':
            if (m5_candles['high'].iloc[-1] - m5_candles['close'].iloc[-1]) > \
               (2 * body_sizes.iloc[-1]):
                return True
        else:
            if (m5_candles['close'].iloc[-1] - m5_candles['low'].iloc[-1]) > \
               (2 * body_sizes.iloc[-1]):
                return True
                
        # 2. Volume spike with reversal
        vol_ma = m5_data['volume'].rolling(20).mean()
        if m5_data['volume'].iloc[-1] > (2 * vol_ma.iloc[-1]):
            if (position_side == 'LONG' and 
                m5_data['close'].iloc[-1] < m5_data['open'].iloc[-1]) or \
               (position_side == 'SHORT' and 
                m5_data['close'].iloc[-1] > m5_data['open'].iloc[-1]):
                return True
                
        # 3. Multiple timeframe momentum alignment
        m1_momentum = self.calculate_momentum(m1_data)
        m5_momentum = self.calculate_momentum(m5_data)
        h1_momentum = self.calculate_momentum(h1_data)
        
        if position_side == 'LONG':
            if m1_momentum < 0 and m5_momentum < 0 and h1_momentum < 0:
                return True
        else:
            if m1_momentum > 0 and m5_momentum > 0 and h1_momentum > 0:
                return True
                
        return False 