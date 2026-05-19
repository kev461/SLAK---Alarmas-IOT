def normalizar(data):
    data["temp"] = max(min(data["temp"], 80), -10)
    data["hum"] = max(min(data["hum"], 100), 0)
    return data