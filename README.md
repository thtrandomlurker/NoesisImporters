# NoesisImporters

A repository of noesis import scripts i've made

# fmt_hypergrind_amd

Imports model files from Go! Go! Hypergrind.

## Format Support

*.amd: ~70% supported. multi-object files are not supported.

*.skn: ~90% supported. Loads automatically if a .skn file is present for the loaded .amd file. currently ignores initial bone rotation and scale

*.ld: ~99% supported. Loads automatically if a .ld animation package is present for the loaded .amd file. Scaling axis is known broken, but low priority.

*.tpl: ~20% supported. Loads automatically if a .tpl texture set is present for the loaded .amd file. currently only works if all textures present uses the CMPR Texture format.

## To-Do

- Implement support for multi-object .amd files
- Implement support for texture formats other than CMPR.

# fmt_mmxcm_four

Imports model files from Megaman X Command Mission (GCN).

## Format Support

*.4: ~100% supported. Vertex positions, normals, uvs, and bone weights are all handled correctly.

*.5: ~15% supported. Skeleton structure is barely understood. bone positions are often completely broken.

## To-Do

- Figure out why the skeleton structure is so confusing

# Helper Scripts

## Archive/MMXCM/arcUnpack.py

Extracts .arc archives from Megaman X Command Mission. usage: `py arcUnpack.py *.arc`
