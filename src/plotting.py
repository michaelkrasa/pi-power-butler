import io

import matplotlib.pyplot as plt
import pandas as pd


def create_price_graph(prices: list[float]) -> bytes:
    """Creates a line chart of electricity prices with conditional coloring."""
    df = pd.DataFrame(prices, columns=["Price (€/MWh)"])
    df.index.name = "Hour"

    # Larger figure for mobile readability
    plt.figure(figsize=(12, 7))
    
    # Set larger font sizes for mobile
    plt.rcParams.update({'font.size': 14})

    # Create a single continuous line with color segments
    x = df.index
    y = df["Price (€/MWh)"]

    # Plot the main line in a neutral color first
    plt.plot(x, y, marker='o', linestyle='-', color='gray', linewidth=3, alpha=0.3)

    # Now overlay colored segments based on price values
    for i in range(len(x) - 1):
        if y.iloc[i] > 0 and y.iloc[i + 1] > 0:
            # Both points positive - red segment
            plt.plot([x[i], x[i + 1]], [y.iloc[i], y.iloc[i + 1]],
                     color='red', linewidth=4, alpha=0.8)
        elif y.iloc[i] <= 0 and y.iloc[i + 1] <= 0:
            # Both points zero/negative - green segment
            plt.plot([x[i], x[i + 1]], [y.iloc[i], y.iloc[i + 1]],
                     color='green', linewidth=4, alpha=0.8)
        else:
            # Transition between positive and negative - use the color of the current point
            color = 'red' if y.iloc[i] > 0 else 'green'
            plt.plot([x[i], x[i + 1]], [y.iloc[i], y.iloc[i + 1]],
                     color=color, linewidth=4, alpha=0.8)

    # Color the markers based on their values
    for i in range(len(x)):
        color = 'red' if y.iloc[i] > 0 else 'green'
        plt.plot(x[i], y.iloc[i], marker='o', color=color, markersize=8, alpha=0.9)

    # Add a horizontal line at zero for reference
    plt.axhline(y=0, color='black', linestyle='--', alpha=0.5, linewidth=1)

    plt.title("Tomorrow's Electricity Prices", fontsize=18, fontweight='bold')
    plt.xlabel("Hour of the Day", fontsize=16)
    plt.ylabel("Price (€/MWh)", fontsize=16)
    plt.grid(True, alpha=0.3)
    plt.xticks(range(0, 24), fontsize=12)
    plt.yticks(fontsize=12)

    # Add legend with larger text
    plt.plot([], [], color='red', linewidth=4, label='Positive prices')
    plt.plot([], [], color='green', linewidth=4, label='Zero/Negative prices')
    plt.legend(fontsize=14, loc='upper right')

    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=100, bbox_inches='tight')
    buf.seek(0)
    plt.close()

    return buf.getvalue()


def create_irradiance_graph(irradiance: list[float]) -> bytes:
    """Creates an area chart of the solar irradiance forecast."""
    df = pd.DataFrame(irradiance, columns=["Irradiance (W/m²)"])
    df.index.name = "Hour"

    # Larger figure for mobile readability
    plt.figure(figsize=(12, 7))
    
    # Set larger font sizes for mobile
    plt.rcParams.update({'font.size': 14})
    
    plt.fill_between(df.index, df["Irradiance (W/m²)"], alpha=0.6, color='orange')
    plt.title("Tomorrow's Solar Irradiance Forecast", fontsize=18, fontweight='bold')
    plt.xlabel("Hour of the Day", fontsize=16)
    plt.ylabel("Irradiance (W/m²)", fontsize=16)
    plt.grid(True, alpha=0.3)
    plt.xticks(range(0, 24), fontsize=12)
    plt.yticks(fontsize=12)

    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=100, bbox_inches='tight')
    buf.seek(0)
    plt.close()

    return buf.getvalue()
