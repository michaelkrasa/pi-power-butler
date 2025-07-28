import io
import matplotlib.pyplot as plt
import pandas as pd

def create_price_graph(prices: list[float]) -> bytes:
    """Creates a line chart of electricity prices."""
    df = pd.DataFrame(prices, columns=["Price (€/MWh)"])
    df.index.name = "Hour"
    
    plt.figure(figsize=(10, 5))
    plt.plot(df.index, df["Price (€/MWh)"], marker='o', linestyle='-')
    plt.title("Tomorrow's Electricity Prices")
    plt.xlabel("Hour of the Day")
    plt.ylabel("Price (€/MWh)")
    plt.grid(True)
    plt.xticks(range(0, 24))
    
    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)
    plt.close()
    
    return buf.getvalue()

def create_irradiance_graph(irradiance: list[float]) -> bytes:
    """Creates an area chart of the solar irradiance forecast."""
    df = pd.DataFrame(irradiance, columns=["Irradiance (W/m²)"])
    df.index.name = "Hour"
    
    plt.figure(figsize=(10, 5))
    plt.fill_between(df.index, df["Irradiance (W/m²)"], alpha=0.5)
    plt.title("Tomorrow's Solar Irradiance Forecast")
    plt.xlabel("Hour of the Day")
    plt.ylabel("Irradiance (W/m²)")
    plt.grid(True)
    plt.xticks(range(0, 24))
    
    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)
    plt.close()
    
    return buf.getvalue()
