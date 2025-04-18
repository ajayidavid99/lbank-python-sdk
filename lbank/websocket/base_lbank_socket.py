import logging
from threading import Thread
from websocket import (
    ABNF,
    create_connection,
    WebSocketException,
    WebSocketConnectionClosedException,
    WebSocketTimeoutException,
)


class LbankSocketHandler(Thread):
    def __init__(
        self,
        base_url,
        on_message=None,
        on_open=None,
        on_close=None,
        on_error=None,
        on_ping=None,
        on_pong=None,
        logger=None,
        timeout=None,
    ):
        Thread.__init__(self)
        if not logger:
            logger = logging.getLogger(__name__)
        self.logger = logger
        self.base_url = base_url
        self.on_message = on_message
        self.on_close = on_close
        self.on_ping = on_ping
        self.on_pong = on_pong
        self.on_open = on_open
        self.on_error = on_error
        self.timeout = timeout

        self.create_ws_connection()

    def create_ws_connection(self):

        self.ws = create_connection(
            self.base_url, timeout=self.timeout
        )
        self._callback(self.on_open)

    def run(self):
        self.read_data()

    def send_message(self, message):
        self.ws.send(message)

    def ping(self):
        self.ws.ping()

    def read_data(self):
        data = ""
        while True:
            try:
                op_code, frame = self.ws.recv_data_frame(True)
            except WebSocketException as e:
                if isinstance(e, WebSocketConnectionClosedException):
                    self.logger.error("Lost websocket connection")
                elif isinstance(e, WebSocketTimeoutException):
                    self.logger.error("Websocket connection timeout")
                else:
                    self.logger.error("Websocket exception: {}".format(e))
                raise e
            except Exception as e:
                self.logger.error("Exception in read_data: {}".format(e))
                raise e

            self._handle_data(op_code, frame, data)
            self._handle_heartbeat(op_code, frame)

            if op_code == ABNF.OPCODE_CLOSE:
                self.logger.warning(
                    "CLOSE frame received, closing websocket connection"
                )
                self._callback(self.on_close)
                break

    def _handle_heartbeat(self, op_code, frame):
        if op_code == ABNF.OPCODE_PING:
            self._callback(self.on_ping, frame.data)
            self.ws.pong("")
            self.logger.debug("Received Ping; PONG frame sent back")
        elif op_code == ABNF.OPCODE_PONG:
            self.logger.debug("Received PONG frame")
            self._callback(self.on_pong)

    def _handle_data(self, op_code, frame, data):
        if op_code == ABNF.OPCODE_TEXT:
            data = frame.data.decode("utf-8")
            # result = json.loads(data)
            self._callback(self.on_message, data)

    def close(self):
        if not self.ws.connected:
            self.logger.warning("Websocket already closed")
        else:
            self.ws.send_close()
        return

    def _callback(self, callback, *args):
        if callback:
            try:
                callback(self, *args)
            except Exception as e:
                self.logger.error(
                    "Error from callback {}: {}".format(callback, e))
                if self.on_error:
                    self.on_error(self, e)
