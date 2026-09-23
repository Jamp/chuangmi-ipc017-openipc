# Comprueba ONVIF en la cámara: GetSystemDateAndTime sin auth, GetDeviceInformation y
# GetStreamUri con PasswordText y PasswordDigest, y si responde a WS-Discovery.
# La contraseña se lee de un fichero para que no aparezca en la línea de órdenes.
#
# Uso: python3 tools/onvif-check.py <ip-de-la-cámara> <usuario> <fichero-con-la-contraseña>
import base64, datetime, hashlib, os, re, socket, sys, urllib.request, uuid

host = sys.argv[1]
user = sys.argv[2]
password = open(sys.argv[3]).read().strip()
device_url = f"http://{host}/onvif/device_service"

WSSE = "http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd"
WSU = "http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd"
PROFILE = "http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-username-token-profile-1.0"


def security_header(mode):
    if mode == "none":
        return ""
    if mode == "text":
        token = f'<Password Type="{PROFILE}#PasswordText">{password}</Password>'
    else:
        nonce = os.urandom(16)
        created = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        digest = base64.b64encode(hashlib.sha1(nonce + created.encode() + password.encode()).digest()).decode()
        token = (f'<Password Type="{PROFILE}#PasswordDigest">{digest}</Password>'
                 f'<Nonce EncodingType="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-soap-message-security-1.0#Base64Binary">{base64.b64encode(nonce).decode()}</Nonce>'
                 f'<Created xmlns="{WSU}">{created}</Created>')
    return f'<s:Header><Security xmlns="{WSSE}"><UsernameToken><Username>{user}</Username>{token}</UsernameToken></Security></s:Header>'


def call(url, body, mode):
    envelope = (f'<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope">'
                f'{security_header(mode)}<s:Body>{body}</s:Body></s:Envelope>')
    request = urllib.request.Request(url, envelope.encode(), {"Content-Type": "application/soap+xml; charset=utf-8"})
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            return response.status, response.read().decode(errors="replace")
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode(errors="replace")


def summary(text):
    fault = re.search(r"<[^>]*Text[^>]*>([^<]+)<", text)
    if "Fault" in text and fault:
        return "FAULT: " + fault.group(1)
    fields = re.findall(r"<[^:>]+:(Manufacturer|Model|FirmwareVersion|Uri|Name|UTCDateTime)>([^<]*)<", text)
    return " ".join(f"{k}={v}" for k, v in fields)[:300] or text[:200]


print("GetSystemDateAndTime, sin auth:", *call(device_url, '<GetSystemDateAndTime xmlns="http://www.onvif.org/ver10/device/wsdl"/>', "none")[:1],
      summary(call(device_url, '<GetSystemDateAndTime xmlns="http://www.onvif.org/ver10/device/wsdl"/>', "none")[1]))
for mode in ("text", "digest"):
    status, text = call(device_url, '<GetDeviceInformation xmlns="http://www.onvif.org/ver10/device/wsdl"/>', mode)
    print(f"GetDeviceInformation, {mode}: HTTP {status}", summary(text))

status, text = call(device_url, '<GetCapabilities xmlns="http://www.onvif.org/ver10/device/wsdl"><Category>Media</Category></GetCapabilities>', "text")
media = re.search(r"<[^:>]+:XAddr>([^<]*media[^<]*)<", text)
media_url = media.group(1) if media else f"http://{host}/onvif/media_service"
print("media service:", media_url)
status, text = call(media_url, '<GetProfiles xmlns="http://www.onvif.org/ver10/media/wsdl"/>', "text")
token = re.search(r'Profiles[^>]*token="([^"]+)"', text)
print(f"GetProfiles, text: HTTP {status}", "token=" + (token.group(1) if token else "?"))
if token:
    body = (f'<GetStreamUri xmlns="http://www.onvif.org/ver10/media/wsdl"><StreamSetup>'
            f'<Stream xmlns="http://www.onvif.org/ver10/schema">RTP-Unicast</Stream>'
            f'<Transport xmlns="http://www.onvif.org/ver10/schema"><Protocol>RTSP</Protocol></Transport>'
            f'</StreamSetup><ProfileToken>{token.group(1)}</ProfileToken></GetStreamUri>')
    for mode in ("text", "digest"):
        status, text = call(media_url, body, mode)
        print(f"GetStreamUri, {mode}: HTTP {status}", summary(text))

probe = (f'<?xml version="1.0" encoding="UTF-8"?><e:Envelope xmlns:e="http://www.w3.org/2003/05/soap-envelope" '
         f'xmlns:w="http://schemas.xmlsoap.org/ws/2004/08/addressing" xmlns:d="http://schemas.xmlsoap.org/ws/2005/04/discovery" '
         f'xmlns:dn="http://www.onvif.org/ver10/network/wsdl"><e:Header><w:MessageID>uuid:{uuid.uuid4()}</w:MessageID>'
         f'<w:To>urn:schemas-xmlsoap-org:ws:2005:04:discovery</w:To><w:Action>http://schemas.xmlsoap.org/ws/2005/04/discovery/Probe</w:Action>'
         f'</e:Header><e:Body><d:Probe><d:Types>dn:NetworkVideoTransmitter</d:Types></d:Probe></e:Body></e:Envelope>')
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
sock.settimeout(4)
sock.sendto(probe.encode(), ("239.255.255.250", 3702))
answers = []
try:
    while True:
        data, address = sock.recvfrom(65535)
        answers.append(address[0])
except socket.timeout:
    pass
print("WS-Discovery: responden", sorted(set(answers)) or "nadie", "| cámara incluida:", host in answers)
