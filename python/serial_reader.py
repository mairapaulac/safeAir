"""
SafeAir - Leitor de Serial
==========================
Modulo responsavel por ler continuamente a porta serial do Arduino em uma
thread separada, sem travar a interface do Streamlit, e manter um historico
das leituras validas em memoria.
"""

import threading
import time
from collections import deque
from datetime import datetime

import serial
import serial.tools.list_ports

STATUS_VALIDOS = ("IDEAL", "ATENCAO", "ALTA", "CRITICO")


def list_available_ports():
    """Retorna a lista de portas seriais disponiveis no sistema (ex: COM3)."""
    return [p.device for p in serial.tools.list_ports.comports()]


def parse_line(raw_line):
    """
    Converte uma linha recebida do Arduino no formato
    'temperatura,umidade,status' em um dicionario.

    Retorna None se a linha estiver mal formada (linhas invalidas sao
    simplesmente ignoradas, conforme esperado durante o boot do Arduino
    ou ruido na serial).
    """
    if not raw_line:
        return None

    parts = raw_line.strip().split(",")
    if len(parts) != 3:
        return None

    temp_str, hum_str, status = parts
    status = status.strip().upper()

    try:
        temperatura = float(temp_str)
        umidade = float(hum_str)
    except ValueError:
        return None

    if status not in STATUS_VALIDOS:
        return None

    return {
        "timestamp": datetime.now(),
        "temperatura": temperatura,
        "umidade": umidade,
        "status": status,
    }


class SerialReader:
    """
    Le a porta serial em background e mantem um historico thread-safe das
    ultimas leituras validas. Detecta desconexao do Arduino (cabo USB
    removido, porta fechada externamente etc.) sem derrubar a aplicacao.
    """

    def __init__(self, port, baud_rate=9600, max_history=300):
        self.port = port
        self.baud_rate = baud_rate
        self.max_history = max_history

        self._serial = None
        self._thread = None
        self._lock = threading.Lock()
        self._running = False
        self._history = deque(maxlen=max_history)
        self._connected = False
        self._last_error = None

    @property
    def is_connected(self):
        return self._connected

    @property
    def last_error(self):
        return self._last_error

    def start(self):
        """Abre a porta serial e inicia a thread de leitura continua."""
        if self._running:
            return

        try:
            self._serial = serial.Serial(self.port, self.baud_rate, timeout=2)
            # O Arduino reinicia ao abrir a serial: aguarda estabilizar
            time.sleep(2)
            self._connected = True
            self._last_error = None
        except serial.SerialException as exc:
            self._connected = False
            self._last_error = str(exc)
            return

        self._running = True
        self._thread = threading.Thread(target=self._read_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """Para a thread de leitura e fecha a porta serial."""
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=2)
        if self._serial is not None and self._serial.is_open:
            self._serial.close()
        self._connected = False

    def _read_loop(self):
        while self._running:
            try:
                raw = self._serial.readline().decode("utf-8", errors="ignore")
                reading = parse_line(raw)
                if reading is not None:
                    with self._lock:
                        self._history.append(reading)
                    self._connected = True
            except (serial.SerialException, OSError) as exc:
                # Arduino desconectado, porta perdida, etc.
                self._connected = False
                self._last_error = str(exc)
                self._running = False
                break

    def get_history(self):
        """Retorna uma copia da lista de leituras (mais antiga -> mais recente)."""
        with self._lock:
            return list(self._history)

    def get_latest(self):
        """Retorna a leitura mais recente, ou None se ainda nao houver dados."""
        with self._lock:
            if not self._history:
                return None
            return self._history[-1]
