"""
This example generates a tetra3 database from a star catalogue. You must have the catalogue file
hip_main.dat in the same directory as tetra3.py to run this example. You can download it from
https://cdsarc.u-strasbg.fr/ftp/cats/I/239/
"""

import sys
sys.path.append('..')

import tetra3

# Create instance without loading any database.
t3 = tetra3.Tetra3(load_database=None)

lens = input("Input your lens focal length in mm ")
camera = input("Your camera, 'ASI' or 'RPI'? ")
if camera.lower() == 'asi':
    fov = 6 * 50/int(float(lens))
    fov_label = str(int(fov - 1))
if camera.lower() == 'rpi':
    fov = 7.5 * 50/int(float(lens))
    fov_label = str(int(fov - 0.5))
print ('filename','t3_fov'+fov_label+'_mag9')
# Generate and save database.
#t3.generate_database(save_as='t3_fov5_mag9', max_fov=6, star_max_magnitude=9, star_catalog='hip_main')
