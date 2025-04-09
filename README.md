# Action-Script-Dumper
Python script to produce a dump of Action Scripts (or Movement Scripts) used in NES and SNES games by HAL Laboratory™, with easy-to-follow macro names.

## How to use.
Simply run the following command (make sure to have Python installed).
```
$ python actscr_dumper16.py <rom_file> <output_file> <data_file>
```
where `rom_file` must be a supported ROM (currently EarthBound and Mother 2), `output_file` is the path to and name of the file where the dump will be saved, and `data_file` is the path to the , namely `modules/<file>.py`.

For example:
```
$ python actscr_dumper16.py EarthBound.smc out/output.txt modules/eb.py
```

For NES games, use the `actscr_dumper8.py` instead (not implemented yet).

## Things not yet implemented.
- Functionality for HAL SNES games aside from Mother 2/EarthBound.
- Functionality for NES games.

## Macro names.
This script dumps out Action Script instructions in a series of specific easy-to-follow format macros, whose names and definitions were made by Catador (CataLatas), you cand find them [here](https://gist.github.com/CataLatas/76700c2781bcfade26953ef4cc827862#file-movscr_codes-ccs).

## Output files.
If you're just for the outputted dumps, here's an updated list of gists for them.
- [EarthBound](https://gist.github.com/Vittorioux/9d7ff0e33f16e78f70432d084e95364d)
- [Mother 2](https://gist.github.com/Vittorioux/914a857ce8943f345d434bbbb0d86154)