import logging
import io
import pandas as pd
import mplfinance as mpf
import matplotlib

# Use a non-interactive backend suitable for server environments
matplotlib.use("Agg")

def generate_trade_chart(
    df: pd.DataFrame,
    signal: dict,
    lookback: int = 120,
    width_px: int = 640
) -> io.BytesIO | None:
    """
    Generates a candlestick chart with trade setup annotations and returns it as an in-memory PNG buffer.

    Args:
        df: DataFrame with OHLCV data. Must have a DatetimeIndex.
        signal: A dictionary containing trade signal details.
        lookback: The number of recent candles to include in the plot.
        width_px: The desired width of the output image in pixels.

    Returns:
        An io.BytesIO buffer containing the PNG image data, or None if generation fails.
    """
    if df.empty or len(df) < 20: # Need a minimum number of candles for a useful plot
        logging.warning("Not enough data to generate a chart.")
        return None

    plot_df = df.tail(lookback).copy()
    symbol = signal.get("symbol", "N/A")
    side = (signal.get("side", "UNKNOWN") or "UNKNOWN").upper()
    entry_price = signal.get("entry_price")
    tp_price = signal.get("take_profit")
    sl_price = signal.get("stop_loss")

    # --- Prepare plot annotations ---
    horizontal_lines = []
    line_colors = []
    if entry_price:
        horizontal_lines.append(entry_price)
        line_colors.append('blue')
    if tp_price:
        horizontal_lines.append(tp_price)
        line_colors.append('green')
    if sl_price:
        horizontal_lines.append(sl_price)
        line_colors.append('red')

    # --- Generate Chart ---
    try:
        # Calculate figure size based on desired pixel width
        # A rough conversion is 100 pixels per inch for `dpi=100`.
        figwidth = width_px / 100
        
        # Create a style object to customize colors
        mc = mpf.make_marketcolors(up='green', down='red', inherit=True)
        s = mpf.make_mpf_style(marketcolors=mc, gridstyle=':')

        fig, _ = mpf.plot(
            plot_df,
            type='candle',
            style=s,
            title=f"{symbol} - {side} Signal",
            ylabel='Price (USDT)',
            volume=True,
            hlines=dict(hlines=horizontal_lines, colors=line_colors, linestyle='--'),
            returnfig=True,
            figsize=(figwidth, figwidth * 0.6), # Maintain a reasonable aspect ratio
            dpi=100
        )

        # Save figure to an in-memory buffer
        buf = io.BytesIO()
        fig.savefig(buf, format='png', bbox_inches='tight')
        buf.seek(0)
        
        # Clear the figure to free up memory
        mpf.plt.close(fig)
        
        return buf

    except Exception as e:
        logging.error(f"Failed to generate chart for {symbol}: {e}", exc_info=True)
        return None 