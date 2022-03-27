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
    mdl.setModelMaterials(NoeModelMaterials([], four.matList))
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
        self.readModel(bs)
    
    def readModel(self, bs):
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
        # test with a full model build, ignoring textures and uvs
        # all of this will be deleted later
        # but will look similar to this, which is mostly copied from my amd script.
        baseIndex = 0
        FaceBuffer = b""
        VertexBuffer = b""
        NormalBuffer = b""
        UVBuffer = b""
        WeightBuffer = b""
        IndexBuffer = b""
        for face in MasterFaceList:
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