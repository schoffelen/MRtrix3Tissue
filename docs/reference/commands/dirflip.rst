.. _dirflip:

dirflip
===========

Synopsis
--------

::

    dirflip [ options ]  in out

-  *in*: the input files for the directions.
-  *out*: the output files for the directions.

Description
-----------

optimise the polarity of the directions in a scheme with respect to a unipolar electrostatic repulsion model, by inversion of individual directions. The orientations themselves are not affected, only their polarity. This is necessary to ensure near-optimal distribution of DW directions for eddy-current correction.

Options
-------

-  **-permutations num** number of permutations to try.

-  **-cartesian** Output the directions in Cartesian coordinates [x y z] instead of [az el].

Standard options
^^^^^^^^^^^^^^^^

-  **-info** display information messages.

-  **-quiet** do not display information messages or progress status.

-  **-debug** display debugging messages.

-  **-force** force overwrite of output files. Caution: Using the same file as input and output might cause unexpected behaviour.

-  **-nthreads number** use this number of threads in multi-threaded applications (set to 0 to disable multi-threading)

-  **-failonwarn** terminate program if a warning is produced

-  **-help** display this information page and exit.

-  **-version** display version information and exit.

--------------



**Author:** J-Donald Tournier (jdtournier@gmail.com)

**Copyright:** Copyright (c) 2008-2016 the MRtrix3 contributors

This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0. If a copy of the MPL was not distributed with this file, You can obtain one at http://mozilla.org/MPL/2.0/

MRtrix is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.

For more details, see www.mrtrix.org
