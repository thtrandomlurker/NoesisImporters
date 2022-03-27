# Script by Thatrandomlurker

from inc_noesis import *
import noesis
import rapi
import struct # for building the buffers
import os # check if file exists

int_Endian = 0

def registerNoesisTypes():
    handle = noesis.register("Megaman X Command Mission Model", ".4")
    noesis.setHandlerTypeCheck(handle, fourCheckType)
    noesis.setHandlerLoadModel(handle, fourLoadModel)
    
    return 1
    
# Determine this can get tricky. best check, if it's larger than expected, le. if still larger, break.
def fourCheckType(data):
    noesis.logPopup()
    bs = NoeBitStream(data)
    if len(data) < 32:
        # doesn't even have all the necessary data.
        return 0
    voCheck = bs.readBytes(4)
    leCheck = struct.unpack("<I", voCheck)[0]
    beCheck = struct.unpack(">I", voCheck)[0]
    if leCheck > len(data):
        if beCheck > len(data):
            # le and be are both bigger than the file itself
            return 0
        else:
            int_Endian = 0
    else:
        int_Endian = 1
    print(int_Endian)
    return 1
    
def fourLoadModel(data, mdlList):
    ctx = rapi.rpgCreateContext()
    fileName = rapi.getExtensionlessName(rapi.getLocalFileName(rapi.getLastCheckedName()))
    filePath = filePath = rapi.getDirForFilePath(rapi.getLastCheckedName())
    four = fourModel(NoeBitStream(data, 1), fileName, filePath)
    try:
        mdl = rapi.rpgConstructModel()
    except:
        mdl = NoeModel()
    mdl.setModelMaterials(NoeModelMaterials(four.texList, four.matList))
    mdl.setBones(four.boneList)
    mdlList.append(mdl)
    return 1
    
class fourModel:
    def __init__(self, bs, fileName, filePath):
        self.matList = []
        self.texList = []
        self.boneList = []
        self.tBoneList = []
        self.tWeightList = []
        self.tIndicesList = []
        # we'll need these to try and load the corresponding "five" files, which contain a model's armature info and possibly animation data.
        self.fileName = fileName
        self.filePath = filePath
        self.tryLoadFive()
        self.tryLoadZeros()
        self.readModel(bs)
    
    def readModel(self, bs):
        rapi.rpgSetOption(noesis.RPGOPT_TRIWINDBACKWARD, 1)
        fileFirst = self.fileName
        VertexBufferOffset = bs.read(">I")[0]
        NormalBufferOffset = bs.read(">I")[0]
        SkinWeightBufferOffset = bs.read(">I")[0]
        UVBufferOffset = bs.read(">I")[0]
        MaterialInfoOffset = bs.read(">I")[0]
        IndexBufferOffset = bs.read(">I")[0]
        VertexCount = bs.read(">H")[0]
        UVCount = bs.read(">H")[0]
        MaterialCount = bs.read(">H")[0]
        TotalFaceCount = bs.read(">H")[0]
        # Vertices
        bs.seek(VertexBufferOffset)
        MeshVerts = []
        for i in range(VertexCount):
            MeshVerts.append(bs.read(">3f"))
        # Normals
        bs.seek(NormalBufferOffset)
        MeshVertNormals = []
        for i in range(VertexCount):
            MeshVertNormals.append(bs.read(">3f"))
        # Skin Weights
        bs.seek(SkinWeightBufferOffset)
        Weights = [[0.0, 0.0]] * VertexCount
        WeightIndices = [[0, 0]] * VertexCount
        for i in range(VertexCount):
            BoneIndex0 = bs.read(">h")[0]
            BoneIndex1 = bs.read(">h")[0]
            BI0Weight = bs.read(">h")[0]
            CountIfFirst = bs.read(">h")[0]
            WeightIndices[i] = [BoneIndex0, BoneIndex1]
            Weights[i] = [BI0Weight / 100, 1.0 - (BI0Weight / 100)]
        # UVs
        bs.seek(UVBufferOffset)
        MeshUVs = []
        for i in range(UVCount):
            MeshUVs.append(bs.read(">2f"))
        # Materials
        bs.seek(MaterialInfoOffset)
        MeshMaterials = []
        for i in range(MaterialCount):
            MaterialName = bytes(reversed(bs.readBytes(8)))
            MaterialName = MaterialName.split(b"\x00")[0].decode("ASCII")
            Unk = bs.read(">I")[0]
            StartFaceIndex = bs.read(">H")[0]
            FaceCount = bs.read(">H")[0]
            # debug
            print("Mat {MatName}: {Start} -> {End}".format(MatName = MaterialName, Start = StartFaceIndex, End = StartFaceIndex + FaceCount))
            MeshMaterials.append({"Name": MaterialName, "StartFace": StartFaceIndex, "FaceCount": FaceCount})
        # Now we need to handle the face data and shove it into the mdl
        # Start simple.
        MasterFaceList = []
        for i in range(TotalFaceCount):
            FaceI0VertIndex = bs.read(">h")[0]
            FaceI0UVIndex = bs.read(">h")[0]
            FaceI1VertIndex = bs.read(">h")[0]
            FaceI1UVIndex = bs.read(">h")[0]
            FaceI2VertIndex = bs.read(">h")[0]
            FaceI2UVIndex = bs.read(">h")[0]
            MasterFaceList.append([[FaceI0VertIndex, FaceI0UVIndex], [FaceI1VertIndex, FaceI1UVIndex], [FaceI2VertIndex, FaceI2UVIndex]])
        
        # now do the real processing.
        for material in MeshMaterials:
            faces = MasterFaceList[material["StartFace"]:material["StartFace"] + material["FaceCount"]]
            baseIndex = 0
            FaceBuffer = b""
            VertexBuffer = b""
            NormalBuffer = b""
            UVBuffer = b""
            WeightBuffer = b""
            IndexBuffer = b""
            for face in faces:
                v1 = MeshVerts[face[0][0]]
                v2 = MeshVerts[face[1][0]]
                v3 = MeshVerts[face[2][0]]
                n1 = MeshVertNormals[face[0][0]]
                n2 = MeshVertNormals[face[1][0]]
                n3 = MeshVertNormals[face[2][0]]
                u1 = MeshUVs[face[0][1]]
                u2 = MeshUVs[face[1][1]]
                u3 = MeshUVs[face[2][1]]
                w1 = Weights[face[0][0]]
                w2 = Weights[face[1][0]]
                w3 = Weights[face[2][0]]
                i1 = WeightIndices[face[0][0]]
                i2 = WeightIndices[face[1][0]]
                i3 = WeightIndices[face[2][0]]
                VertexBuffer += struct.pack("fff", v1[0], v1[1]*-1, v1[2]*-1)
                VertexBuffer += struct.pack("fff", v2[0], v2[1]*-1, v2[2]*-1)
                VertexBuffer += struct.pack("fff", v3[0], v3[1]*-1, v3[2]*-1)
                NormalBuffer += struct.pack("fff", n1[0], n1[1], n1[2])
                NormalBuffer += struct.pack("fff", n2[0], n2[1], n2[2])
                NormalBuffer += struct.pack("fff", n3[0], n3[1], n3[2])
                UVBuffer += struct.pack("ff", u1[0], u1[1])
                UVBuffer += struct.pack("ff", u2[0], u2[1])
                UVBuffer += struct.pack("ff", u3[0], u3[1])
                WeightBuffer += struct.pack("ff", w1[0], w1[1])
                WeightBuffer += struct.pack("ff", w2[0], w2[1])
                WeightBuffer += struct.pack("ff", w3[0], w3[1])
                IndexBuffer += struct.pack("ii", i1[0], i1[1])
                IndexBuffer += struct.pack("ii", i2[0], i2[1])
                IndexBuffer += struct.pack("ii", i3[0], i3[1])
                FaceBuffer += struct.pack("hhh", baseIndex, baseIndex+1, baseIndex+2)
                baseIndex += 3
            rapi.rpgBindPositionBuffer(VertexBuffer, noesis.RPGEODATA_FLOAT, 12)
            rapi.rpgBindNormalBuffer(NormalBuffer, noesis.RPGEODATA_FLOAT, 12)
            rapi.rpgBindUV1Buffer(UVBuffer, noesis.RPGEODATA_FLOAT, 8)
            rapi.rpgBindBoneWeightBuffer(WeightBuffer, noesis.RPGEODATA_FLOAT, 8, 2)
            rapi.rpgBindBoneIndexBuffer(IndexBuffer, noesis.RPGEODATA_INT, 8, 2)
            rapi.rpgSetMaterial(material["Name"])
            mat = NoeMaterial(material["Name"], material["Name"])
            mat.setTexture(material["Name"])
            self.matList.append(mat)
            rapi.rpgCommitTriangles(FaceBuffer, noesis.RPGEODATA_USHORT, int(len(FaceBuffer)/2), noesis.RPGEO_TRIANGLE)
        
    def tryLoadFive(self):
        five = fiveAnimator()
        try:
            # usually a model has multiple parts, but only one "animator"
            # so, we list out all .5 files in the folder
            # if the name of the .5 is in the filename of the active model, then it's likely correct
            print(os.listdir(self.filePath))
            fivename = [file for file in os.listdir(self.filePath) if file.split('.')[1] == "5" and file.split('.')[0] in self.fileName][0]  # god damn this list comprehension is extreme. but it should mostly work
            print(fivename)
            bss = rapi.loadIntoByteArray(self.filePath + fivename)
        except:
            self.boneList = []
        else:
            bs = NoeBitStream(bss, 1)
            five.readFive(bs)
            self.boneList = five.Bones
            
    def tryLoadZeros(self):
        # each tpl ("0") in this game contains seemingly exactly one texture
        ZeroFiles = [file for file in os.listdir(self.filePath) if file.endswith(".0")]
        print(ZeroFiles)
        # load the textures
        for file in ZeroFiles:
            bss = rapi.loadIntoByteArray(self.filePath + file)
            bs = NoeBitStream(bss, 1)
            tTPL = TexturePaletteLibrary()
            tTPL.LoadTextures(bs, file)
            # should only be one but still
            for tex in tTPL.Textures:
                tex.name = file.split('.')[0]
                self.texList.append(tex)
                print(tex)
        
class fiveAnimator:
    def __init__(self):
        self.Bones = []
        
    def readFive(self, bs):
        Positions = []
        Unk01 = bs.read(">I")[0]
        Unk02 = bs.read(">I")[0]
        Unk03 = bs.read(">I")[0]
        Unk04 = bs.read(">I")[0]
        BoneCount = bs.read(">H")[0]
        Unk06 = bs.read(">H")[0]
        Unk07 = bs.read(">I")[0]
        Unk08 = bs.read(">I")[0]
        for i in range(BoneCount):
            Parent = bs.read(">h")[0]
            bUnk01 = noesis.getFloat16(bs.read(">h")[0])
            bUnk02 = noesis.getFloat16(bs.read(">h")[0])
            bUnk03 = noesis.getFloat16(bs.read(">h")[0])
            BonePos = bs.read(">3f")
            print(Parent, bUnk01, bUnk02, bUnk03, BonePos)
            if bUnk01 == 0.0 and bUnk02 == 2.0 and bUnk03 == 0.0:
                boneMTX = NoeMat43((NoeVec3((1.0, 0.0, 0.0)), NoeVec3((0.0, 1.0, 0.0)), NoeVec3((0.0, 0.0, 1.0)), NoeVec3((BonePos[2], BonePos[1], BonePos[0]))))
            else:
                boneMTX = NoeMat43((NoeVec3((1.0, 0.0, 0.0)), NoeVec3((0.0, 1.0, 0.0)), NoeVec3((0.0, 0.0, 1.0)), NoeVec3((BonePos[0], BonePos[1], BonePos[2]))))
            Bone = NoeBone(i, str("Bone_") + str(i), boneMTX, str("Bone_") + str(Parent), Parent)
            self.Bones.append(Bone)

# copy TPL code from amd script
class TPLImage:
    def __init__(self):
        self.Height = 0xFFFF
        self.Width = 0xFFFF
        self.ImageFormat = 0xFFFFFFFF
        self._internalTexOffset = 0xFFFFFFFF
        self.WrapS = 0xFFFFFFFF
        self.WrapT = 0xFFFFFFFF
        self.MinFilter = 0xFFFFFFFF
        self.MagFilter = 0xFFFFFFFF
        self.LODBias = 0
        self.EdgeLODEnable = 0xFF
        self.MinLOD = 0xFF
        self.MaxLOD = 0xFF
        self.Unpacked = 0xFF
        self.ImageData = b''  # Stores raw RGBA once finished reading
    def ReadImageMD(self, bs):
        self.Height = bs.readUShort()
        self.Width = bs.readUShort()
        self.ImageFormat = bs.readUInt()
        self._internalTexOffset = bs.readUInt()
        self.WrapS = bs.readUInt()
        self.WrapT = bs.readUInt()
        self.MinFilter = bs.readUInt()
        self.MagFilter = bs.readUInt()
        self.LODBias = bs.readFloat()
        self.EdgeLODEnable = bs.readUByte()
        self.MinLOD = bs.readUByte()
        self.MaxLOD = bs.readUByte()
        self.Unpacked = bs.readUByte()
        
    def ReadCMPR(self, bs):
        bs.seek(self._internalTexOffset)
        appxImageSize = (int(self.Height / 8) * int(self.Width / 8)) * 32  # round height/width to next ^2, divide by block width and block height for format, multiply by block size in bytes
        #print(appxImageSize)
        chunkWidth = int(self.Width / 8)
        chunkHeight = int(self.Height / 8)
        # ensure width and height aren't 0
        if chunkWidth == 0:
            chunkWidth = 1
        if chunkHeight == 0:
            chunkHeight = 1
        print(chunkWidth, chunkHeight)
        BlockCount = int(appxImageSize / 32)  # should always hold true as long as an accurate image size is calculated
        Blocks = []  # List of blocks
        chunkRows = []
        for i in range(chunkHeight):
            row = []
            Block = []
            for j in range(chunkWidth):
                tSubBlocks = []
                for k in range(4):
                    palette = []
                    SP1Short = bs.readUShort()
                    SP2Short = bs.readUShort()
                    # First, let's get the rgb value for SP1
                    SP1Bits = format(SP1Short, 'b').zfill(16)
                    #print(SP1Bits)
                    SP1R = int(SP1Bits[0:5], 2) * 0x8
                    SP1G = int(SP1Bits[5:11], 2) * 0x4
                    SP1B = int(SP1Bits[11:], 2) * 0x8
                    #print(SP1R, SP1G, SP1B)
                    # Next, SP2
                    SP2Bits = format(SP2Short, 'b').zfill(16)
                    #print(SP2Bits)
                    SP2R = int(SP2Bits[0:5], 2) * 0x8
                    SP2G = int(SP2Bits[5:11], 2) * 0x4
                    SP2B = int(SP2Bits[11:], 2) * 0x8
                    #print(SP2R, SP2G, SP2B)
                    # Now we detect interpolation method
                    if SP1Short > SP2Short:
                        SP3R = int(SP2R + ((SP1R - SP2R) * 0.6666666666666))
                        SP3G = int(SP2G + ((SP1G - SP2G) * 0.6666666666666))
                        SP3B = int(SP2B + ((SP1B - SP2B) * 0.6666666666666))
                        SP4R = int(SP2R + ((SP1R - SP2R) * 0.3333333333333))
                        SP4G = int(SP2G + ((SP1G - SP2G) * 0.3333333333333))
                        SP4B = int(SP2B + ((SP1B - SP2B) * 0.3333333333333))
                        palette.append([[SP1R, SP1G, SP1B, 255], [SP2R, SP2G, SP2B, 255], [SP3R, SP3G, SP3B, 255], [SP4R, SP4G, SP4B, 255]])
                    else:
                        SP3R = int(SP2R + ((SP1R - SP2R) * 0.6666666666666))
                        SP3G = int(SP2G + ((SP1G - SP2G) * 0.6666666666666))
                        SP3B = int(SP2B + ((SP1B - SP2B) * 0.6666666666666))
                        SP4R = int(0)
                        SP4G = int(0)
                        SP4B = int(0)
                        palette.append([[SP1R, SP1G, SP1B, 255], [SP2R, SP2G, SP2B, 255], [SP3R, SP3G, SP3B, 255], [SP4R, SP4G, SP4B, 0]])
                    
                    SubBlockIndicesBits = format(bs.readUInt(), 'b').zfill(32)
                    SubBlockIndices = []
                    for l in range(4):
                        Row = []
                        IndPart = SubBlockIndicesBits[l * 8:((l + 1)*8)+1]
                        Row.append(int(IndPart[0:2], 2))
                        Row.append(int(IndPart[2:4], 2))
                        Row.append(int(IndPart[4:6], 2))
                        Row.append(int(IndPart[6:8], 2))
                        SubBlockIndices.append(Row)
                    #print(SubBlockIndices)
                    tSubBlocks.append([SubBlockIndices, palette])
                Block.append([[tSubBlocks[0], tSubBlocks[1]], [tSubBlocks[2], tSubBlocks[3]]])
            chunkRows.append(Block)
        # Assemble into an RGBA32 Image file
        # First off, we need the chunk width (how many chunks from left to right)
        # this is easy with some math
        #oRows = []
        oPixels = b''
        for h in range(chunkHeight):
            block = chunkRows[h]
            r1b = b''
            r2b = b''
            r3b = b''
            r4b = b''
            r5b = b''
            r6b = b''
            r7b = b''
            r8b = b''
            for w in range(chunkWidth):
                tSub_UL = block[w][0][0]
                tSub_UR = block[w][0][1]
                tSub_DL = block[w][1][0]
                tSub_DR = block[w][1][1]
                for i in range(4):
                    r1b += struct.pack("BBBB", tSub_UL[1][0][tSub_UL[0][0][i]][0], tSub_UL[1][0][tSub_UL[0][0][i]][1], tSub_UL[1][0][tSub_UL[0][0][i]][2], tSub_UL[1][0][tSub_UL[0][0][i]][3])
                for i in range(4):
                    r1b += struct.pack("BBBB", tSub_UR[1][0][tSub_UR[0][0][i]][0], tSub_UR[1][0][tSub_UR[0][0][i]][1], tSub_UR[1][0][tSub_UR[0][0][i]][2], tSub_UR[1][0][tSub_UR[0][0][i]][3])
                for i in range(4):
                    r2b += struct.pack("BBBB", tSub_UL[1][0][tSub_UL[0][1][i]][0], tSub_UL[1][0][tSub_UL[0][1][i]][1], tSub_UL[1][0][tSub_UL[0][1][i]][2], tSub_UL[1][0][tSub_UL[0][1][i]][3])
                for i in range(4):
                    r2b += struct.pack("BBBB", tSub_UR[1][0][tSub_UR[0][1][i]][0], tSub_UR[1][0][tSub_UR[0][1][i]][1], tSub_UR[1][0][tSub_UR[0][1][i]][2], tSub_UR[1][0][tSub_UR[0][1][i]][3])
                for i in range(4):
                    r3b += struct.pack("BBBB", tSub_UL[1][0][tSub_UL[0][2][i]][0], tSub_UL[1][0][tSub_UL[0][2][i]][1], tSub_UL[1][0][tSub_UL[0][2][i]][2], tSub_UL[1][0][tSub_UL[0][2][i]][3])
                for i in range(4):
                    r3b += struct.pack("BBBB", tSub_UR[1][0][tSub_UR[0][2][i]][0], tSub_UR[1][0][tSub_UR[0][2][i]][1], tSub_UR[1][0][tSub_UR[0][2][i]][2], tSub_UR[1][0][tSub_UR[0][2][i]][3])
                for i in range(4):
                    r4b += struct.pack("BBBB", tSub_UL[1][0][tSub_UL[0][3][i]][0], tSub_UL[1][0][tSub_UL[0][3][i]][1], tSub_UL[1][0][tSub_UL[0][3][i]][2], tSub_UL[1][0][tSub_UL[0][3][i]][3])
                for i in range(4):
                    r4b += struct.pack("BBBB", tSub_UR[1][0][tSub_UR[0][3][i]][0], tSub_UR[1][0][tSub_UR[0][3][i]][1], tSub_UR[1][0][tSub_UR[0][3][i]][2], tSub_UR[1][0][tSub_UR[0][3][i]][3])
                for i in range(4):
                    r5b += struct.pack("BBBB", tSub_DL[1][0][tSub_DL[0][0][i]][0], tSub_DL[1][0][tSub_DL[0][0][i]][1], tSub_DL[1][0][tSub_DL[0][0][i]][2], tSub_DL[1][0][tSub_DL[0][0][i]][3])
                for i in range(4):
                    r5b += struct.pack("BBBB", tSub_DR[1][0][tSub_DR[0][0][i]][0], tSub_DR[1][0][tSub_DR[0][0][i]][1], tSub_DR[1][0][tSub_DR[0][0][i]][2], tSub_DR[1][0][tSub_DR[0][0][i]][3])
                for i in range(4):
                    r6b += struct.pack("BBBB", tSub_DL[1][0][tSub_DL[0][1][i]][0], tSub_DL[1][0][tSub_DL[0][1][i]][1], tSub_DL[1][0][tSub_DL[0][1][i]][2], tSub_DL[1][0][tSub_DL[0][1][i]][3])
                for i in range(4):
                    r6b += struct.pack("BBBB", tSub_DR[1][0][tSub_DR[0][1][i]][0], tSub_DR[1][0][tSub_DR[0][1][i]][1], tSub_DR[1][0][tSub_DR[0][1][i]][2], tSub_DR[1][0][tSub_DR[0][1][i]][3])
                for i in range(4):
                    r7b += struct.pack("BBBB", tSub_DL[1][0][tSub_DL[0][2][i]][0], tSub_DL[1][0][tSub_DL[0][2][i]][1], tSub_DL[1][0][tSub_DL[0][2][i]][2], tSub_DL[1][0][tSub_DL[0][2][i]][3])
                for i in range(4):
                    r7b += struct.pack("BBBB", tSub_DR[1][0][tSub_DR[0][2][i]][0], tSub_DR[1][0][tSub_DR[0][2][i]][1], tSub_DR[1][0][tSub_DR[0][2][i]][2], tSub_DR[1][0][tSub_DR[0][2][i]][3])
                for i in range(4):
                    r8b += struct.pack("BBBB", tSub_DL[1][0][tSub_DL[0][3][i]][0], tSub_DL[1][0][tSub_DL[0][3][i]][1], tSub_DL[1][0][tSub_DL[0][3][i]][2], tSub_DL[1][0][tSub_DL[0][3][i]][3])
                for i in range(4):
                    r8b += struct.pack("BBBB", tSub_DR[1][0][tSub_DR[0][3][i]][0], tSub_DR[1][0][tSub_DR[0][3][i]][1], tSub_DR[1][0][tSub_DR[0][3][i]][2], tSub_DR[1][0][tSub_DR[0][3][i]][3])
                #row1.append(tSub_UL[1][0][tSub_UL[0][0][0]])
                #row1.append(tSub_UL[1][0][tSub_UL[0][0][1]])
                #row1.append(tSub_UL[1][0][tSub_UL[0][0][2]])
                #row1.append(tSub_UL[1][0][tSub_UL[0][0][3]])
                #row1.append(tSub_UR[1][0][tSub_UR[0][0][0]])
                #row1.append(tSub_UR[1][0][tSub_UR[0][0][1]])
                #row1.append(tSub_UR[1][0][tSub_UR[0][0][2]])
                #row1.append(tSub_UR[1][0][tSub_UR[0][0][3]])
                #row2.append(tSub_UL[1][0][tSub_UL[0][1][0]])
                #row2.append(tSub_UL[1][0][tSub_UL[0][1][1]])
                #row2.append(tSub_UL[1][0][tSub_UL[0][1][2]])
                #row2.append(tSub_UL[1][0][tSub_UL[0][1][3]])
                #row2.append(tSub_UR[1][0][tSub_UR[0][1][0]])
                #row2.append(tSub_UR[1][0][tSub_UR[0][1][1]])
                #row2.append(tSub_UR[1][0][tSub_UR[0][1][2]])
                #row2.append(tSub_UR[1][0][tSub_UR[0][1][3]])
                #row3.append(tSub_UL[1][0][tSub_UL[0][2][0]])
                #row3.append(tSub_UL[1][0][tSub_UL[0][2][1]])
                #row3.append(tSub_UL[1][0][tSub_UL[0][2][2]])
                #row3.append(tSub_UL[1][0][tSub_UL[0][2][3]])
                #row3.append(tSub_UR[1][0][tSub_UR[0][2][0]])
                #row3.append(tSub_UR[1][0][tSub_UR[0][2][1]])
                #row3.append(tSub_UR[1][0][tSub_UR[0][2][2]])
                #row3.append(tSub_UR[1][0][tSub_UR[0][2][3]])
                #row4.append(tSub_UL[1][0][tSub_UL[0][3][0]])
                #row4.append(tSub_UL[1][0][tSub_UL[0][3][1]])
                #row4.append(tSub_UL[1][0][tSub_UL[0][3][2]])
                #row4.append(tSub_UL[1][0][tSub_UL[0][3][3]])
                #row4.append(tSub_UR[1][0][tSub_UR[0][3][0]])
                #row4.append(tSub_UR[1][0][tSub_UR[0][3][1]])
                #row4.append(tSub_UR[1][0][tSub_UR[0][3][2]])
                #row4.append(tSub_UR[1][0][tSub_UR[0][3][3]])
                #row5.append(tSub_DL[1][0][tSub_DL[0][0][0]])
                #row5.append(tSub_DL[1][0][tSub_DL[0][0][1]])
                #row5.append(tSub_DL[1][0][tSub_DL[0][0][2]])
                #row5.append(tSub_DL[1][0][tSub_DL[0][0][3]])
                #row5.append(tSub_DR[1][0][tSub_DR[0][0][0]])
                #row5.append(tSub_DR[1][0][tSub_DR[0][0][1]])
                #row5.append(tSub_DR[1][0][tSub_DR[0][0][2]])
                #row5.append(tSub_DR[1][0][tSub_DR[0][0][3]])
                #row6.append(tSub_DL[1][0][tSub_DL[0][1][0]])
                #row6.append(tSub_DL[1][0][tSub_DL[0][1][1]])
                #row6.append(tSub_DL[1][0][tSub_DL[0][1][2]])
                #row6.append(tSub_DL[1][0][tSub_DL[0][1][3]])
                #row6.append(tSub_DR[1][0][tSub_DR[0][1][0]])
                #row6.append(tSub_DR[1][0][tSub_DR[0][1][1]])
                #row6.append(tSub_DR[1][0][tSub_DR[0][1][2]])
                #row6.append(tSub_DR[1][0][tSub_DR[0][1][3]])
                #row7.append(tSub_DL[1][0][tSub_DL[0][2][0]])
                #row7.append(tSub_DL[1][0][tSub_DL[0][2][1]])
                #row7.append(tSub_DL[1][0][tSub_DL[0][2][2]])
                #row7.append(tSub_DL[1][0][tSub_DL[0][2][3]])
                #row7.append(tSub_DR[1][0][tSub_DR[0][2][0]])
                #row7.append(tSub_DR[1][0][tSub_DR[0][2][1]])
                #row7.append(tSub_DR[1][0][tSub_DR[0][2][2]])
                #row7.append(tSub_DR[1][0][tSub_DR[0][2][3]])
                #row8.append(tSub_DL[1][0][tSub_DL[0][3][0]])
                #row8.append(tSub_DL[1][0][tSub_DL[0][3][1]])
                #row8.append(tSub_DL[1][0][tSub_DL[0][3][2]])
                #row8.append(tSub_DL[1][0][tSub_DL[0][3][3]])
                #row8.append(tSub_DR[1][0][tSub_DR[0][3][0]])
                #row8.append(tSub_DR[1][0][tSub_DR[0][3][1]])
                #row8.append(tSub_DR[1][0][tSub_DR[0][3][2]])
                #row8.append(tSub_DR[1][0][tSub_DR[0][3][3]])
            oPixels += r1b
            oPixels += r2b
            oPixels += r3b
            oPixels += r4b
            oPixels += r5b
            oPixels += r6b
            oPixels += r7b
            oPixels += r8b
        self.ImageData = bytes(oPixels[0:(self.Width * self.Height) * 4])
        
    def ReadC8(self, bs, PalHeadOffset):
        # get palette data
        palette = []
        bs.seek(PalHeadOffset)
        EntryCount = bs.read(">H")[0]
        Unpacked = bs.read("B")[0]
        pad = bs.read("B")[0]
        PaletteFormat = bs.read(">I")[0]
        PaletteOffset = bs.read(">I")[0]
        bs.seek(PaletteOffset)
        if PaletteFormat == 1:
            for i in range(256):
                ColShort = bs.readUShort()
                ColBits = format(ColShort, 'b').zfill(16)
                R = int(ColBits[0:5], 2) * 0x8
                G = int(ColBits[5:11], 2) * 0x4
                B = int(ColBits[11:], 2) * 0x8
                palette.append(struct.pack("BBBB", R, G, B, 255))
        # now setup the data
        bs.seek(self._internalTexOffset)
        oPixels = b""
        chunkWidth = int(self.Width / 8)
        chunkHeight = int(self.Height / 4)
        for h in range(chunkHeight):
            row0 = b""
            row1 = b""
            row2 = b""
            row3 = b""
            for w in range(chunkWidth):
                r00 = bs.readBytes(1)[0]
                r01 = bs.readBytes(1)[0]
                r02 = bs.readBytes(1)[0]
                r03 = bs.readBytes(1)[0]
                r04 = bs.readBytes(1)[0]
                r05 = bs.readBytes(1)[0]
                r06 = bs.readBytes(1)[0]
                r07 = bs.readBytes(1)[0]
                r10 = bs.readBytes(1)[0]
                r11 = bs.readBytes(1)[0]
                r12 = bs.readBytes(1)[0]
                r13 = bs.readBytes(1)[0]
                r14 = bs.readBytes(1)[0]
                r15 = bs.readBytes(1)[0]
                r16 = bs.readBytes(1)[0]
                r17 = bs.readBytes(1)[0]
                r20 = bs.readBytes(1)[0]
                r21 = bs.readBytes(1)[0]
                r22 = bs.readBytes(1)[0]
                r23 = bs.readBytes(1)[0]
                r24 = bs.readBytes(1)[0]
                r25 = bs.readBytes(1)[0]
                r26 = bs.readBytes(1)[0]
                r27 = bs.readBytes(1)[0]
                r30 = bs.readBytes(1)[0]
                r31 = bs.readBytes(1)[0]
                r32 = bs.readBytes(1)[0]
                r33 = bs.readBytes(1)[0]
                r34 = bs.readBytes(1)[0]
                r35 = bs.readBytes(1)[0]
                r36 = bs.readBytes(1)[0]
                r37 = bs.readBytes(1)[0]
                row0 += palette[r00]
                row0 += palette[r01]
                row0 += palette[r02]
                row0 += palette[r03]
                row0 += palette[r04]
                row0 += palette[r05]
                row0 += palette[r06]
                row0 += palette[r07]
                row1 += palette[r10]
                row1 += palette[r11]
                row1 += palette[r12]
                row1 += palette[r13]
                row1 += palette[r14]
                row1 += palette[r15]
                row1 += palette[r16]
                row1 += palette[r17]
                row2 += palette[r20]
                row2 += palette[r21]
                row2 += palette[r22]
                row2 += palette[r23]
                row2 += palette[r24]
                row2 += palette[r25]
                row2 += palette[r26]
                row2 += palette[r27]
                row3 += palette[r30]
                row3 += palette[r31]
                row3 += palette[r32]
                row3 += palette[r33]
                row3 += palette[r34]
                row3 += palette[r35]
                row3 += palette[r36]
                row3 += palette[r37]
            oPixels += row0
            oPixels += row1
            oPixels += row2
            oPixels += row3
        self.ImageData = bytes(oPixels[0:(self.Width * self.Height) * 4])
        
class TexturePaletteLibrary:
    def __init__(self):
        self.Textures = []
        
    def LoadTextures(self, bs, fileName):
        magic = bs.readBytes(4)
        if magic != b"\x00\x20\xAF\x30":
            return 0  # invalid file.
        TextureCount = bs.readUInt()
        TexInfoOffset = bs.readUInt()
        bs.seek(TexInfoOffset)
        for i in range(TextureCount):
            TexHeadOffset = bs.readUInt()
            PalHeadOffset = bs.readUInt()
            print(PalHeadOffset)
            # get current position
            cursor = bs.tell()
            bs.seek(TexHeadOffset)
            Image = TPLImage()
            Image.ReadImageMD(bs)
            print(Image.ImageFormat, "this line")
            print(Image.Width, Image.Height)
            if Image.ImageFormat == 14:
                Image.ReadCMPR(bs)
            elif Image.ImageFormat == 9:
                Image.ReadC8(bs, PalHeadOffset)
            # now that we have the image data, we can work it into a noesis texture
            # pack into format
            noeTexData = rapi.imageEncodeRaw(Image.ImageData, Image.Width, Image.Height, 'r8g8b8a8')
            texture = NoeTexture(fileName + "_" + str(i), Image.Width, Image.Height, noeTexData, noesis.NOESISTEX_RGBA32)
            self.Textures.append(texture)
            bs.seek(cursor)