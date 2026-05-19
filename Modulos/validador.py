CAMPOS = ["gas","llama","temp","hum","luz","sonido","peligro"]

def validar(data):
    for c in CAMPOS:
        if c not in data:
            print("Falta:", c)
            return False

    if not isinstance(data["temp"], (int, float)):
        return False

    if data["hum"] < 0 or data["hum"] > 100:
        return False

    return True