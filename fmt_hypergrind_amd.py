# Script by Thatrandomlurker/RhythmProtogen

from inc_noesis import *
import noesis
import rapi
import struct  # for building the buffers
import os # check if file exists

int_Endian = 0

def registerNoesisTypes():
    handle = noesis.register("Go! Go! Hypergrind Model", ".amd")
    noesis.setHandlerTypeCheck(handle, amdCheckType)
    noesis.setHandlerLoadModel(handle, amdLoadModel)
    
    return 1
# Check that this is a supported file. won't immediately break if the model is a different format than expected, but will log a notice.
def amdCheckType(data):
    bs = NoeBitStream(data, 1)
    if len(data) < 4:
        # Clearly it's an invalid file, it doesn't even have the version
        return 0
    Version = bs.readFloat()
    if Version != 2.0:
        print("File version is not 2.0. can't guarantee this will work")
        #
    Magic = bs.readBytes(4)
    print(Magic)
    if Magic != b'AMD\x00':
        # Definitely not a valid AMD file
        return 0
    return 1

def amdLoadModel(data, mdlList):
    ctx = rapi.rpgCreateContext()
    fileName = rapi.getExtensionlessName(rapi.getLocalFileName(rapi.getLastCheckedName()))
    filePath = rapi.getDirForFilePath(rapi.getLastCheckedName())
    amd = amdModel(NoeBitStream(data, 1), fileName, filePath)
    try:
        mdl = rapi.rpgConstructModel()
    except:
        mdl = NoeModel()
    print(amd.texList)
    print(amd.matList)
    mdl.setModelMaterials(NoeModelMaterials(amd.texList, amd.matList))
    mdl.setBones(amd.boneList)
    mdlList.append(mdl)
    return 1
    

class amdModel:
    def __init__(self, bs, fileName, filePath):
        self.matList = []
        self.texList = []
        self.boneList = []
        self.tBoneList = []
        self.tWeightList = []
        self.tIndicesList = []
        # fileName and filePath are used for texture names, and loading additional data not stored within the amd file itself, such as skeleton + skinning data.
        self.fileName = fileName
        self.filePath = filePath
        # Skin data has to come first to ensure all verts are weighted
        self.tryLoadSkin()
        self.readModel(bs)
        self.tryLoadTextures()
        
    def readModel(self, bs):
        # set this ahead of time
        rapi.rpgSetOption(noesis.RPGOPT_TRIWINDBACKWARD, 1)
        fileFirst = self.fileName
        Version = bs.read(">f")
        Magic = bs.readBytes(4)
        modelCount = bs.readInt()
        modelOffset = bs.readInt()
        UnkCount = bs.readInt()  # honestly no clue what this is meant to do. i know that it points to a set of values for each submesh regardless of split models.
        UnkOffset = bs.readInt()  # this is the pointer to it. 
        bs.seek(modelOffset, NOESEEK_ABS)  # jump straight to model reading
        # keep it limited to one model for now, handle more later
        SubmeshCount = bs.readInt()
        VertexCount = bs.readShort()
        NormalCount = bs.readShort()
        VertColorCount = bs.readShort()
        UVCount = bs.readShort()
        SubmeshInfoOffset = bs.readInt()
        VertexOffset = bs.readInt()
        NormalOffset = bs.readInt()
        VertColorOffset = bs.readInt()
        UVOffset = bs.readInt()
        # Vertex stuff is easy to handle
        bs.seek(VertexOffset, NOESEEK_ABS)
        # now read data
        MeshVerts = []
        for i in range(VertexCount):
            MeshVerts.append(bs.read(">3f"))
        bs.seek(NormalOffset, NOESEEK_ABS)
        MeshVertNormals = []
        for i in range(NormalCount):
            MeshVertNormals.append(bs.read(">3f"))
        bs.seek(VertColorOffset, NOESEEK_ABS)
        MeshVertColors = []
        for i in range(VertColorCount):
            MeshVertColors.append(bs.read(">4B"))
        bs.seek(UVOffset, NOESEEK_ABS)
        MeshUVs = []
        for i in range(UVCount):
            MeshUVs.append(bs.read(">2f"))
        bs.seek(SubmeshInfoOffset, NOESEEK_ABS)
        MeshSubmeshes = []
        for i in range(SubmeshCount):
            SubmeshUnk = bs.readInt()
            TexIndex = bs.readShort()
            bs.seek(10, NOESEEK_REL)
            # some floats
            unkFloats = bs.read(">4f")
            FaceDataSize = bs.readInt()
            FaceDataOffset = bs.readInt()
            bs.seek(8, NOESEEK_REL)  # skip two nulls(?)
            cur = bs.tell()  # know where to return to once this submesh has been read
            bs.seek(FaceDataOffset, NOESEEK_ABS)
            faces = []
            while True:
                FaceChunkType = bs.readShort()
                if FaceChunkType == 0:
                    break
                FaceChunkCount = bs.readShort()
                RemainingFaces = FaceChunkCount - 3
                # Initial Face
                f1 = bs.read(">4h")
                f2 = bs.read(">4h")
                f3 = bs.read(">4h")
                faces.append([f1, f2, f3])
                preBase = f2
                base = f3
                reverseOrder = True
                while RemainingFaces != 0:
                    if reverseOrder:
                        f3 = bs.read(">4h")
                        faces.append([base, preBase, f3])
                        preBase = base
                        base = f3
                        RemainingFaces -= 1
                        reverseOrder = False
                    else:
                        f3 = bs.read(">4h")
                        faces.append([preBase, base, f3])
                        preBase = base
                        base = f3
                        RemainingFaces -= 1
                        reverseOrder = True
            MeshSubmeshes.append([TexIndex, faces])
            bs.seek(cur, NOESEEK_ABS)
            
        #Confirm data is valid
        #print(len(MeshVertNormalsFull))
        #print(len(MeshVertColorsFull))
        #print(len(MeshUVsFull))
        
        # now let's try building the buffers
        for submesh in MeshSubmeshes:
            baseIndex = 0
            FaceBuffer = b''
            VertexBuffer = b''
            NormalBuffer = b''
            ColorBuffer = b''
            UVBuffer = b''
            WeightBuffer = b''
            IndexBuffer = b''
            texIdx = submesh[0]
            for face in submesh[1]:
                v1 = MeshVerts[face[0][0]]
                v2 = MeshVerts[face[1][0]]
                v3 = MeshVerts[face[2][0]]
                n1 = MeshVertNormals[face[0][1]]
                n2 = MeshVertNormals[face[1][1]]
                n3 = MeshVertNormals[face[2][1]]
                c1 = MeshVertColors[face[0][2]]
                c2 = MeshVertColors[face[1][2]]
                c3 = MeshVertColors[face[2][2]]
                u1 = MeshUVs[face[0][3]]
                u2 = MeshUVs[face[1][3]]
                u3 = MeshUVs[face[2][3]]
                if len(self.tWeightList) != 0:
                    print(face[0][0], face[1][0], face[2][0])
                    w1 = self.tWeightList[face[0][0]]
                    print(w1)
                    w2 = self.tWeightList[face[1][0]]
                    print(w2)
                    w3 = self.tWeightList[face[2][0]]
                    print(w3)
                    i1 = self.tIndicesList[face[0][0]]
                    i2 = self.tIndicesList[face[1][0]]
                    i3 = self.tIndicesList[face[2][0]]
                VertexBuffer += struct.pack("fff", v1[0], v1[1], v1[2])
                VertexBuffer += struct.pack("fff", v2[0], v2[1], v2[2])
                VertexBuffer += struct.pack("fff", v3[0], v3[1], v3[2])
                NormalBuffer += struct.pack("fff", n1[0], n1[1], n1[2])
                NormalBuffer += struct.pack("fff", n2[0], n2[1], n2[2])
                NormalBuffer += struct.pack("fff", n3[0], n3[1], n3[2])
                ColorBuffer += struct.pack("ffff", c1[0] / 255, c1[1] / 255, c1[2] / 255, c1[3] / 255)
                ColorBuffer += struct.pack("ffff", c2[0] / 255, c2[1] / 255, c2[2] / 255, c2[3] / 255)
                ColorBuffer += struct.pack("ffff", c3[0] / 255, c3[1] / 255, c3[2] / 255, c3[3] / 255)
                UVBuffer += struct.pack("ff", u1[0], u1[1])
                UVBuffer += struct.pack("ff", u2[0], u2[1])
                UVBuffer += struct.pack("ff", u3[0], u3[1])
                if len(self.tWeightList) != 0:
                    WeightBuffer += struct.pack("ffff", w1[0], w1[1], w1[2], w1[3])
                    WeightBuffer += struct.pack("ffff", w2[0], w2[1], w2[2], w2[3])
                    WeightBuffer += struct.pack("ffff", w3[0], w3[1], w3[2], w3[3])
                    IndexBuffer += struct.pack("iiii", i1[0], i1[1], i1[2], i1[3])
                    IndexBuffer += struct.pack("iiii", i2[0], i2[1], i2[2], i2[3])
                    IndexBuffer += struct.pack("iiii", i3[0], i3[1], i3[2], i3[3])
                FaceBuffer += struct.pack("hhh", baseIndex, baseIndex+1, baseIndex+2)
                baseIndex += 3
        
            rapi.rpgBindPositionBuffer(VertexBuffer, noesis.RPGEODATA_FLOAT, 12)
            rapi.rpgBindNormalBuffer(NormalBuffer, noesis.RPGEODATA_FLOAT, 12)
            rapi.rpgBindUV1Buffer(UVBuffer, noesis.RPGEODATA_FLOAT, 8)
            rapi.rpgBindColorBuffer(ColorBuffer, noesis.RPGEODATA_FLOAT, 16, 4)
            if len(self.tWeightList) != 0:
                rapi.rpgBindBoneWeightBuffer(WeightBuffer, noesis.RPGEODATA_FLOAT, 16, 4)
                rapi.rpgBindBoneIndexBuffer(IndexBuffer, noesis.RPGEODATA_INT, 16, 4)
            rapi.rpgSetMaterial(fileFirst + "_" + str(texIdx))
            mat = NoeMaterial(fileFirst + "_" + str(texIdx), "")
            mat.setTexture(fileFirst + "_" + str(texIdx))
            self.matList.append(mat)
            rapi.rpgCommitTriangles(FaceBuffer, noesis.RPGEODATA_USHORT, int(len(FaceBuffer)/2), noesis.RPGEO_TRIANGLE)
    def tryLoadSkin(self):
        SKN = SkinData()
        try:
            print(self.filePath + self.fileName + ".skn")
            bss = rapi.loadIntoByteArray(self.filePath + self.fileName + ".skn")
        except:
            self.boneList = []
        else:
            bs = NoeBitStream(bss, 1)
            SKN.readSkinInfo(bs)
            self.boneList = SKN.Bones
            self.tWeightList = SKN.Weights
            self.tIndicesList = SKN.WeightIndices
    
    def tryLoadTextures(self):
        TPLFile = TexturePaletteLibrary()
        try:
            print(self.filePath + self.fileName + ".tpl")
            bss = rapi.loadIntoByteArray(self.filePath + self.fileName + ".tpl")
        except:
            self.texList = []
        else:
            bs = NoeBitStream(bss, 1)
            TPLFile.LoadTextures(bs, self.fileName)
            self.texList = TPLFile.Textures

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
        self.ImageData = oPixels
        
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
            # since we're working with CMPR exclusively atm, we can skip for now
            cursor = bs.tell()
            bs.seek(TexHeadOffset)
            Image = TPLImage()
            Image.ReadImageMD(bs)
            Image.ReadCMPR(bs)
            # now that we have the image data, we can work it into a noesis texture
            # pack into format
            noeTexData = rapi.imageEncodeRaw(Image.ImageData, Image.Width, Image.Height, 'r8g8b8a8')
            texture = NoeTexture(fileName + "_" + str(i), Image.Width, Image.Height, noeTexData, noesis.NOESISTEX_RGBA32)
            self.Textures.append(texture)
            bs.seek(cursor)
                
class SkinData:
    def __init__(self):
        self.Bones = []
        self.Weights = []
        self.WeightIndices = []

    def readSkinInfo(self, bs):
        FileVersion = bs.readFloat()
        FileMagic = bs.readBytes(4)
        BoneCount = bs.readUInt()
        BoneOffset = bs.readUInt()
        SingleWeightsCount = bs.readUInt()
        SingleWeightsOffset = bs.readUInt()
        DoubleWeightsCount = bs.readUInt()
        DoubleWeightsOffset = bs.readUInt()
        TripleWeightsCount = bs.readUInt()
        TripleWeightsOffset = bs.readUInt()
        QuadWeightsCount = bs.readUInt()
        QuadWeightsOffset = bs.readUInt()
        sumWeightCount = SingleWeightsCount + DoubleWeightsCount + TripleWeightsCount + QuadWeightsCount
        self.Weights = [[0, 0, 0, 0]] * sumWeightCount
        self.WeightIndices = [[0, 0, 0, 0]] * sumWeightCount
        # read bone stuff first
        bs.seek(BoneOffset)
        BoneParentTable = []
        BoneOffsetsTable = []
        for i in range(BoneCount):
            Parent = bs.readInt()
            bs.seek(0x10, NOESEEK_REL)
            Position = bs.read(">3f")
            bs.seek(0x0C, NOESEEK_REL)
            BoneParentTable.append(Parent)
            BoneOffsetsTable.append(Position)
        BonePositionsTable = []
        idx = 0
        while idx < len(BoneOffsetsTable):
            itm = BoneOffsetsTable[idx]
            par = BoneParentTable[idx]
            if par != -1:
                parTable = [par]
                curPar = par
                while True:
                    nextPar = BoneParentTable[curPar]
                    if nextPar == -1:
                        break
                    else:
                        parTable.append(nextPar)
                        curPar = nextPar
                print(idx, parTable)
                position_0 = itm[0]
                position_1 = itm[1]
                position_2 = itm[2]
                for item in parTable:
                    position_0 += BoneOffsetsTable[item][0]
                    position_1 += BoneOffsetsTable[item][1]
                    position_2 += BoneOffsetsTable[item][2]
                BonePositionsTable.append([position_0, position_1, position_2])
            else:
                BonePositionsTable.append(itm)
            idx += 1
        # Ok,we have positions, we have parents, now we need to make this a format that noesis will accept
        for i in range(BoneCount):
            # create bone
            # This game doesn't use names for bones, so we can just directly use indices as names
            boneMTX = NoeMat43((NoeVec3((1.0, 0.0, 0.0)), NoeVec3((0.0, 1.0, 0.0)), NoeVec3((0.0, 0.0, 1.0)), NoeVec3(tuple(BonePositionsTable[i]))))
            
            Bone = NoeBone(i, str("Bone_") + str(i), boneMTX, str("Bone_") + str(BoneParentTable[i]), BoneParentTable[i])
            self.Bones.append(Bone)
            
        # now to handle skin weights
        # best option is to normalize to a length of 4 on all verts
        bs.seek(SingleWeightsOffset, NOESEEK_ABS)
        for i in range(SingleWeightsCount):
            v1 = bs.readUInt()
            v2 = bs.readUInt()
            indicesOffset = bs.readUInt()
            weightsOffset = bs.readUInt()
            cur = bs.tell()
            bs.seek(indicesOffset)
            indices = bs.read(">h")
            bs.seek(weightsOffset)
            weights = bs.read(">f")
            bs.seek(cur)
            self.Weights[v1] = [weights[0], 0, 0, 0]
            self.WeightIndices[v1] = [indices[0], 0, 0, 0]
        bs.seek(DoubleWeightsOffset, NOESEEK_ABS)
        for i in range(DoubleWeightsCount):
            v1 = bs.readUInt()
            v2 = bs.readUInt()
            indicesOffset = bs.readUInt()
            weightsOffset = bs.readUInt()
            cur = bs.tell()
            bs.seek(indicesOffset)
            indices = bs.read(">hh")
            bs.seek(weightsOffset)
            weights = bs.read(">ff")
            bs.seek(cur)
            self.Weights[v1] = [weights[0], weights[1], 0, 0]
            self.WeightIndices[v1] = [indices[0], indices[1], 0, 0]
        bs.seek(TripleWeightsOffset, NOESEEK_ABS)
        for i in range(TripleWeightsCount):
            v1 = bs.readUInt()
            v2 = bs.readUInt()
            indicesOffset = bs.readUInt()
            weightsOffset = bs.readUInt()
            cur = bs.tell()
            bs.seek(indicesOffset)
            indices = bs.read(">hhh")
            bs.seek(weightsOffset)
            weights = bs.read(">fff")
            bs.seek(cur)
            self.Weights[v1] = [weights[0], weights[1], weights[2], 0]
            self.WeightIndices[v1] = [indices[0], indices[1], indices[2], 0]
        bs.seek(QuadWeightsOffset, NOESEEK_ABS)
        for i in range(QuadWeightsCount):
            v1 = bs.readUInt()
            v2 = bs.readUInt()
            indicesOffset = bs.readUInt()
            weightsOffset = bs.readUInt()
            cur = bs.tell()
            bs.seek(indicesOffset)
            indices = bs.read(">hhhh")
            bs.seek(weightsOffset)
            weights = bs.read(">ffff")
            bs.seek(cur)
            self.Weights[v1] = [weights[0], weights[1], weights[2], weights[3]]
            self.WeightIndices[v1] = [indices[0], indices[1], indices[2], indices[3]]