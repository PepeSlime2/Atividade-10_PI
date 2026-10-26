"""
Mostra no terminal as leituras do DHT11 enviadas pela Heltec via USB.
Não salva nada no banco: só os dados do rádio (via MQTT) vão para o Mongo.

Instalar:  pip install pyserial
Rodar:     python main.py            (detecta a porta sozinho)
           python main.py COM5       (Windows, porta manual)
           python main.py /dev/ttyUSB0  (Linux)
"""
import json
import sys
from datetime import datetime

import serial
import serial.tools.list_ports

BAUD = 115200


def achar_porta():
    portas = list(serial.tools.list_ports.comports())
    # Prioriza o CH340 do Arduino Mega; a Meshtastic (USB nativo) só cospe log de debug
    for p in portas:
        if "ch340" in f"{p.description} {p.manufacturer}".lower():
            return p.device
    # Chips USB-serial comuns na Heltec: CP210x (V2) e CH9102/CH340 (V3)
    for p in portas:
        desc = f"{p.description} {p.manufacturer}".lower()
        if any(c in desc for c in ("cp210", "ch910", "ch340", "usb", "uart")):
            return p.device
    if portas:
        return portas[0].device
    sys.exit("Nenhuma porta serial encontrada. A placa está conectada?")


def main():
    porta = sys.argv[1] if len(sys.argv) > 1 else achar_porta()
    print(f"Conectando em {porta} @ {BAUD}... (Ctrl+C para sair)\n")

    with serial.Serial(porta, BAUD, timeout=5) as ser:
        while True:
            linha = ser.readline().decode("utf-8", errors="ignore").strip()
            if not linha:
                continue

            hora = datetime.now().strftime("%H:%M:%S")

            if linha.startswith("#"):          # mensagens/erros do ESP
                print(f"[{hora}] {linha[1:].strip()}")
                continue

            # O Mega manda "Enviado: {"t":..,"u":..}"; a Heltec mandava {"temp":..,"umid":..}
            inicio = linha.find("{")
            try:
                d = json.loads(linha[inicio:]) if inicio >= 0 else None
                temp = d.get("temp", d.get("t"))
                umid = d.get("umid", d.get("u"))
                print(f"[{hora}] Temperatura: {temp:5.1f} °C | "
                      f"Umidade: {umid:5.1f} %")
            except (json.JSONDecodeError, AttributeError, TypeError, ValueError):
                print(f"[{hora}] (bruto) {linha}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nEncerrado.")
    except serial.SerialException as e:
        sys.exit(f"Erro na serial: {e}\n(Feche o Monitor Serial da Arduino IDE, ele trava a porta.)")