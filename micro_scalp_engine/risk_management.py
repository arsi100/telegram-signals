import logging

def calculate_dynamic_position_size(
    account_equity: float,
    stop_loss_price: float,
    entry_price: float,
    max_risk_per_trade_pct: float = 0.005, # Risk 0.5% of equity per trade
    total_portfolio_risk_pct: float = 0.02, # Max 2% total exposure across all trades
    open_positions_risk: float = 0.0 # Sum of risk from all other open positions
) -> float:
    """
    Calculates the position size in the base currency (e.g., USDT) based on a dynamic risk model.

    Args:
        account_equity: The total current value of the trading account.
        stop_loss_price: The price at which the trade will be exited for a loss.
        entry_price: The planned entry price for the asset.
        max_risk_per_trade_pct: The maximum percentage of account equity to risk on this single trade.
        total_portfolio_risk_pct: The maximum percentage of account equity to have at risk across all open positions.
        open_positions_risk: The current sum of risk percentages from other open trades.

    Returns:
        The calculated position size to use for the trade, or 0.0 if the trade would exceed risk limits.
    """
    if entry_price <= 0 or stop_loss_price <= 0 or account_equity <= 0:
        return 0.0

    # 1. Determine the maximum available risk for this new trade
    available_portfolio_risk = total_portfolio_risk_pct - open_positions_risk
    if available_portfolio_risk <= 0:
        logging.warning("Cannot open new position: Total portfolio risk limit has been reached.")
        return 0.0
    
    # The risk for this trade is the lesser of the per-trade limit and the available portfolio risk
    risk_for_this_trade_pct = min(max_risk_per_trade_pct, available_portfolio_risk)
    
    # 2. Calculate the dollar amount to risk
    amount_to_risk = account_equity * risk_for_this_trade_pct

    # 3. Calculate the distance to the stop-loss as a percentage
    stop_loss_distance_pct = abs(entry_price - stop_loss_price) / entry_price
    if stop_loss_distance_pct == 0:
        logging.error("Stop-loss distance is zero. Cannot calculate position size to avoid division by zero.")
        return 0.0

    # 4. Calculate the total position size
    # Position Size = (Amount to Risk) / (Stop-Loss Distance Percentage)
    position_size = amount_to_risk / stop_loss_distance_pct
    
    # 5. Final check: ensure the calculated position size doesn't exceed total equity
    if position_size > account_equity:
        logging.warning(f"Calculated position size ({position_size:.2f}) exceeds account equity ({account_equity:.2f}). Capping at equity.")
        position_size = account_equity

    logging.info(
        f"Calculated Position Size: {position_size:.2f} USDT. "
        f"Risking {amount_to_risk:.2f} USDT ({risk_for_this_trade_pct:.2%}) "
        f"with SL distance of {stop_loss_distance_pct:.2%}."
    )
    
    return position_size 