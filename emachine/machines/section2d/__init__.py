"""
General 2D sections of electrical machines (T59, T60), meshed with Gmsh for the 2D Elmer solver.

    radial.py   a radial machine as rings from the bore outwards (stators and rotors, any number of
                air gaps): slotted stators with tooth tips, notches and split teeth, salient stators;
                rotors with surface, Halbach, consequent-pole, interior-V, spoke, flux-barrier (with or
                without magnets), salient and through-magnet layouts
    axial.py    an axial machine as unrolled slices at several radii (quasi-3D), periodic around
    mesher.py   fragments the faces, names the regions, meshes, writes <out>.msh and <out>.regions.json

A section is described by a plain dictionary (see radial.build and axial.build); the regions of the
mesh carry what the solver needs: kind (core, coil, magnet, air), side (stator, rotor), coil phase,
sign and share, magnet magnetisation (unit vector in the plane) and remanence, and the air-gap bands
with the side of their rotor for the torque.
"""
