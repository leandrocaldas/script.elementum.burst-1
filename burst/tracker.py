import time
import hashlib
import socket
import random
from struct import error, pack, unpack
from kodi_six import xbmcgui
from elementum.provider import log
from future.utils import PY3
import base64
if PY3:
    from urllib.parse import urlparse, quote
else:
    from urlparse import urlparse
    from urllib import quote

# ref: https://github.com/ngosang/trackerslist

TR_OPENTR = ('tracker.opentrackr.org', 1337)
TR_OPENTR_URL = 'udp://tracker.opentrackr.org:1337/announce'

TR_DEMONII = ('open.demonii.com', 1337)
TR_DEMONII_URL = 'udp://open.demonii.com:1337/announce'

TR_STEALTH = ('open.stealth.si', 80)
TR_STEALTH_URL = 'udp://open.stealth.si:80/announce'

TR_EXPLODIE = ('explodie.org', 6969)
TR_EXPLODIE_URL = 'udp://explodie.org:6969/announce'

TR_OPENTRACKER = ('opentracker.io', 6969)
TR_OPENTRACKER_URL = 'udp://opentracker.io:6969/announce'

TR_DLER = ('tracker.dler.org', 6969)
TR_DLER_URL = 'udp://tracker.dler.org:6969/announce'

TR_TIMEOUT = 0.6  # Alinhado com main.yml

TR_AND = '&tr='
TR_FULL_STR = quote(
    TR_AND + TR_OPENTR_URL +
    TR_AND + TR_DEMONII_URL +
    TR_AND + TR_STEALTH_URL +
    TR_AND + TR_EXPLODIE_URL +
    TR_AND + TR_OPENTRACKER_URL +
    TR_AND + TR_DLER_URL
)

class UdpTrackerAnnounceOutput:
    def __init__(self):
        self.action = None
        self.transaction_id = None
        self.interval = None
        self.leechers = None
        self.seeders = None

    def from_bytes(self, payload, expected_trans_id):
        if len(payload) < 20:
            print('BURST_TRACKER - Payload muito curto: %d bytes' % len(payload))
            return False
        try:
            self.action, self.transaction_id, self.interval, self.leechers, self.seeders = unpack('>LLLLL', payload[:20])
            if self.action != 1:
                print('BURST_TRACKER - Resposta não é announce, action=%d' % self.action)
                return False
            if self.transaction_id != expected_trans_id:
                print('BURST_TRACKER - Transaction ID mismatch: esperado=%d, recebido=%d' % 
                      (expected_trans_id, self.transaction_id))
                return False
            if self.leechers > 1000000 or self.seeders > 1000000:
                print('BURST_TRACKER - Valores absurdos: Leechers=%d, Seeders=%d' % 
                      (self.leechers, self.seeders))
                return False
            print('BURST_TRACKER - Extraído: Action=%d, TransactionID=%d, Interval=%d, Leechers=%d, Seeders=%d' % 
                  (self.action, self.transaction_id, self.interval, self.leechers, self.seeders))
            return True
        except Exception as e:
            print('BURST_TRACKER - Falha ao desempacotar payload: %s - Payload: %s' % (e, payload))
            return False

class UdpTrackerConnection:
    def __init__(self):
        self.conn_id = pack('>Q', 0x41727101980)
        self.action = pack('>I', 0)
        self.trans_id = pack('>I', random.randint(0, 2**32 - 1))

    def to_bytes(self):
        return self.conn_id + self.action + self.trans_id
        
    def from_bytes(self, payload):
        try:
            self.action, self.trans_id, self.conn_id = unpack('>LLQ', payload[:16])
            return True
        except Exception as e:
            print('BURST_TRACKER - UdpTrackerConnection from_bytes() falhou - %s' % e)
            return False

def _read_from_socket(sock):
    data = b''
    try:
        buff = sock.recv(4096)
        print("BURST_TRACKER - Resposta recebida: %s" % buff)
        data += buff
    except socket.timeout as e:
        print("BURST_TRACKER - Timeout ao ler do socket: %s" % e)
    except socket.error as e:
        print("BURST_TRACKER - Erro de socket: %s" % e)
    except Exception as e:
        print('BURST_TRACKER - _read_from_socket falhou - %s' % e)
    return data

class UdpTrackerAnnounce:
    def __init__(self, info_hash, conn_id, peer_id):
        self.peer_id = peer_id
        self.conn_id = conn_id
        self.info_hash = info_hash
        self.trans_id = pack('>I', random.randint(0, 2**32 - 1))
        self.action = pack('>I', 1)

    def to_bytes(self):
        conn_id = pack('>Q', self.conn_id)
        action = self.action
        trans_id = self.trans_id
        downloaded = pack('>Q', 0)
        left = pack('>Q', 0)
        uploaded = pack('>Q', 0)
        event = pack('>I', 0)
        ip = pack('>I', 0)
        key = pack('>I', random.randint(0, 2**32 - 1))
        num_want = pack('>i', -1)
        port = pack('>H', 6881)  # Porta padrão BitTorrent, alinhada com main.yml
        msg = (conn_id + action + trans_id + self.info_hash + self.peer_id + downloaded +
               left + uploaded + event + ip + key + num_want + port)
        return msg

def get_torrent_info(torrent_obj):
    hash = torrent_obj['info_hash']
    name = torrent_obj['name']

    print('BURST_TRACKER - Hash bruto: %s' % hash)
    if len(hash) == 40:
        try:
            new_hash = bytearray.fromhex(hash)
            print('BURST_TRACKER - Hash hex decodificado: %s' % new_hash)
        except ValueError:
            print('BURST_TRACKER - Falha na decodificação hex')
            return (hash, -1, -1)
    elif len(hash) == 32:
        try:
            new_hash = bytearray(base64.b32decode(hash.upper()))
            print('BURST_TRACKER - Hash base32 decodificado: %s' % new_hash)
        except Exception as e:
            print('BURST_TRACKER - Falha na decodificação base32: %s' % e)
            return (hash, -1, -1)
    else:
        print('BURST_TRACKER - Comprimento de hash inválido: %d' % len(hash))
        return (hash, -1, -1)

    if len(new_hash) != 20:
        print('BURST_TRACKER - Tamanho de hash inválido após decodificação: %d' % len(new_hash))
        return (hash, -1, -1)

    peer_id = b"-GT0001-" + bytes(random.randint(0, 9) for _ in range(13))  # Alinhado com main.yml
    print('BURST_TRACKER - Peer ID usado: %s' % peer_id)

    results = []
    trackers = [
        (TR_OPENTR[0], TR_OPENTR[1]),
        (TR_DEMONII[0], TR_DEMONII[1]),
        (TR_STEALTH[0], TR_STEALTH[1]),
        (TR_EXPLODIE[0], TR_EXPLODIE[1]),
        (TR_OPENTRACKER[0], TR_OPENTRACKER[1]),
        (TR_DLER[0], TR_DLER[1]),
    ]
    for ip, port in trackers:
        result = get_info_from_tracker(new_hash, peer_id, ip, port)
        print('BURST_TRACKER - Resultado do tracker %s:%d - %s' % (ip, port, result))
        if result:
            results.append(result)

    s_array = [x[0] for x in results if x is not None]
    num_s = max(s_array) if len(s_array) > 0 else -1

    l_array = [x[1] for x in results if x is not None]
    num_l = max(l_array) if len(l_array) > 0 else -1

    # Calculate total peers as sum of max seeders and max leechers
    num_p = (num_s + num_l) if (num_s >= 0 and num_l >= 0) else -1

    print('BURST_TRACKER - Números para %s %s - Seeders: %s, Leechers: %s, Total Peers: %s' % (name, hash, num_s, num_l, num_p))

    return (hash, num_s, num_p)

def get_info_from_tracker(hash, peer_id, ip, port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.settimeout(TR_TIMEOUT)

    tracker_connection_input = UdpTrackerConnection()
    message = tracker_connection_input.to_bytes()
    print('BURST_TRACKER - Enviando mensagem de conexão para %s:%d' % (ip, port))
    try:
        sock.sendto(message, (ip, port))
    except Exception as e:
        print('BURST_TRACKER - Falha no sock.sendto para %s:%d - %s' % (ip, port, e))
        sock.close()
        return None

    try:
        response = _read_from_socket(sock)
        print('BURST_TRACKER - Resposta bruta do tracker: %s' % response)
        if not response:
            print('BURST_TRACKER - Sem resposta para conexão UDP: %s:%d' % (ip, port))
            sock.close()
            return None
    except socket.timeout as e:
        print('BURST_TRACKER - Timeout para %s:%d - %s' % (ip, port, e))
        sock.close()
        return None
    except Exception as e:
        print('BURST_TRACKER - Erro inesperado ao ler de %s:%d - %s' % (ip, port, e))
        sock.close()
        return None

    res = UdpTrackerConnection()
    if not res.from_bytes(response):
        print('BURST_TRACKER - Falha ao processar resposta de conexão: %s:%d' % (ip, port))
        sock.close()
        return None

    if res.action != 0:
        print('BURST_TRACKER - Resposta de conexão inválida, action=%d: %s:%d' % (res.action, ip, port))
        sock.close()
        return None

    conn_id = res.conn_id
    print('BURST_TRACKER - Connection ID usado: %s' % conn_id)

    try:
        tracker_announce_input = UdpTrackerAnnounce(hash, conn_id, peer_id)
        print('BURST_TRACKER - Enviando announce para %s:%d' % (ip, port))
        sock.sendto(tracker_announce_input.to_bytes(), (ip, port))
        response = _read_from_socket(sock)
        print('BURST_TRACKER - Resposta de announce: %s' % response)
    except Exception as e:
        print('BURST_TRACKER - Falha no announce para %s:%d - %s' % (ip, port, e))
        sock.close()
        return None

    if not response:
        print('BURST_TRACKER - Sem resposta para UdpTrackerAnnounce: %s:%d' % (ip, port))
        sock.close()
        return None

    try:
        tracker_announce_output = UdpTrackerAnnounceOutput()
        if not tracker_announce_output.from_bytes(response, unpack('>I', tracker_announce_input.trans_id)[0]):
            print('BURST_TRACKER - Falha ao processar saída de announce para %s:%d' % (ip, port))
            sock.close()
            return None
        if tracker_announce_output.leechers is not None and tracker_announce_output.leechers >= 0:
            print('BURST_TRACKER - Leechers válidos: %d' % tracker_announce_output.leechers)
            sock.close()
            return (tracker_announce_output.seeders, tracker_announce_output.leechers)
        else:
            print('BURST_TRACKER - Leechers inválido: %d' % tracker_announce_output.leechers)
            sock.close()
            return (tracker_announce_output.seeders, 0)
    except Exception as e:
        print('BURST_TRACKER - Falha ao processar saída de announce para %s:%d - %s' % (ip, port, e))
        sock.close()
        return None
