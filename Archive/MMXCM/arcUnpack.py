import struct
import sys
import os

if not os.path.exists(sys.argv[1].split('.')[0]):
    os.mkdir(sys.argv[1].split('.')[0])

with open(sys.argv[1], 'rb') as f:
    while True:
        revName = f.read(8)
        if revName == b'':
            print("fuck the last file massively overshot.")
            break
        if revName == b'\x00\x00\x00\x00\x00\x00\x00\x00':
            print("End of File Reached.")
            break
        encName = bytes(reversed(revName))
        fileName = encName.split(b'\x00')[0].decode("ASCII")
        print(f.tell()-8, fileName)
        unk = struct.unpack(">H", f.read(2))[0]
        fileType = struct.unpack(">H", f.read(2))[0]
        fileSize = struct.unpack(">I", f.read(4))[0]
        f.seek(16, 1)
        with open(f"{sys.argv[1].split('.')[0]}/{fileName}.{fileType}", 'wb') as o:
            o.write(f.read(fileSize))
        