# Copyright (c) 2019 Thijs Dhollander and The Florey Institute
# of Neuroscience and Mental Health, Melbourne, Australia.
#
# This Software is provided on an "as is" basis, without
# warranty of any kind, either expressed, implied, or
# statutory, including, without limitation, warranties that
# the Software is free of defects, merchantable, fit for a
# particular purpose or non-infringing.

def usage(base_parser, subparsers): #pylint: disable=unused-variable
  parser = subparsers.add_parser('dholl_old', parents=[base_parser])
  parser.set_author('Thijs Dhollander (thijs.dhollander@gmail.com)')
  parser.set_copyright('Copyright (c) 2019 Thijs Dhollander and The Florey Institute of Neuroscience and Mental Health, Melbourne, Australia. This Software is provided on an \"as is\" basis, without warranty of any kind, either expressed, implied, or statutory, including, without limitation, warranties that the Software is free of defects, merchantable, fit for a particular purpose or non-infringing.')
  parser.set_synopsis('The OLD Dhollander et al. (2016) algorithm for unsupervised estimation of WM, GM and CSF response functions.')
  parser.add_citation('Dhollander, T.; Raffelt, D. & Connelly, A. Unsupervised 3-tissue response function estimation from single-shell or multi-shell diffusion MR data without a co-registered T1 image. ISMRM Workshop on Breaking the Barriers of Diffusion MRI, 2016, 5')
  parser.add_description('This is the OLD version of the Dhollander et al. (2016) algorithm. This version of the algorithm is deprecated and will disappear again in a future version of the software. Use \"dwi2response dhollander\" instead, which runs the new and improved 2019 algorithm.')
  parser.add_argument('input', help='Input DWI dataset')
  parser.add_argument('out_sfwm', help='Output single-fibre WM response function text file')
  parser.add_argument('out_gm', help='Output GM response function text file')
  parser.add_argument('out_csf', help='Output CSF response function text file')
  options = parser.add_argument_group('Options for the \'dholl_old\' algorithm')
  options.add_argument('-erode', type=int, default=3, help='Number of erosion passes to apply to initial (whole brain) mask. Set to 0 to not erode the brain mask. (default: 3)')
  options.add_argument('-fa', type=float, default=0.2, help='FA threshold for crude WM versus GM-CSF separation. (default: 0.2)')
  options.add_argument('-sfwm', type=float, default=0.5, help='Final number of single-fibre WM voxels to select, as a percentage of refined WM. (default: 0.5 per cent)')
  options.add_argument('-gm', type=float, default=2.0, help='Final number of GM voxels to select, as a percentage of refined GM. (default: 2 per cent)')
  options.add_argument('-csf', type=float, default=10.0, help='Final number of CSF voxels to select, as a percentage of refined CSF. (default: 10 per cent)')



def check_output_paths(): #pylint: disable=unused-variable
  from mrtrix3 import app
  app.check_output_path(app.ARGS.out_sfwm)
  app.check_output_path(app.ARGS.out_gm)
  app.check_output_path(app.ARGS.out_csf)



def get_inputs(): #pylint: disable=unused-variable
  pass



def needs_single_shell(): #pylint: disable=unused-variable
  return False



def execute(): #pylint: disable=unused-variable
  from mrtrix3 import app, image, matrix, MRtrixError, path, run


  # CHECK INPUTS AND OPTIONS
  app.console('-------')

  # Get b-values and number of volumes per b-value.
  bvalues = [ int(round(float(x))) for x in image.mrinfo('dwi.mif', 'shell_bvalues').split() ]
  bvolumes = [ int(x) for x in image.mrinfo('dwi.mif', 'shell_sizes').split() ]
  app.console(str(len(bvalues)) + ' unique b-value(s) detected: ' + ','.join(map(str,bvalues)) + ' with ' + ','.join(map(str,bvolumes)) + ' volumes')
  if len(bvalues) < 2:
    raise MRtrixError('Need at least 2 unique b-values (including b=0).')
  bvalues_option = ' -shells ' + ','.join(map(str,bvalues))

  # Get lmax information (if provided).
  sfwm_lmax = [ ]
  if app.ARGS.lmax:
    sfwm_lmax = [ int(x.strip()) for x in app.ARGS.lmax.split(',') ]
    if not len(sfwm_lmax) == len(bvalues):
      raise MRtrixError('Number of lmax\'s (' + str(len(sfwm_lmax)) + ', as supplied to the -lmax option: ' + ','.join(map(str,sfwm_lmax)) + ') does not match number of unique b-values.')
    for sfl in sfwm_lmax:
      if sfl%2:
        raise MRtrixError('Values supplied to the -lmax option must be even.')
      if sfl<0:
        raise MRtrixError('Values supplied to the -lmax option must be non-negative.')
  sfwm_lmax_option = ''
  if sfwm_lmax:
    sfwm_lmax_option = ' -lmax ' + ','.join(map(str,sfwm_lmax))


  # PREPARATION
  app.console('-------')
  app.console('Preparation:')

  # Erode (brain) mask.
  if app.ARGS.erode > 0:
    app.console('* Eroding brain mask by ' + str(app.ARGS.erode) + ' pass(es)...')
    run.command('maskfilter mask.mif erode eroded_mask.mif -npass ' + str(app.ARGS.erode), show=False)
  else:
    app.console('Not eroding brain mask.')
    run.command('mrconvert mask.mif eroded_mask.mif -datatype bit', show=False)
  statmaskcount = image.statistic('mask.mif', 'count', '-mask mask.mif')
  statemaskcount = image.statistic('eroded_mask.mif', 'count', '-mask eroded_mask.mif')
  app.console('  [ mask: ' + str(statmaskcount) + ' -> ' + str(statemaskcount) + ' ]')

  # Get volumes, compute mean signal and SDM per b-value; compute overall SDM; get rid of erroneous values.
  app.console('* Computing signal decay metric (SDM):')
  totvolumes = 0
  fullsdmcmd = 'mrcalc'
  errcmd = 'mrcalc'
  zeropath = 'mean_b' + str(bvalues[0]) + '.mif'
  for ibv, bval in enumerate(bvalues):
    app.console(' * b=' + str(bval) + '...')
    meanpath = 'mean_b' + str(bval) + '.mif'
    run.command('dwiextract dwi.mif -shells ' + str(bval) + ' - | mrmath - mean ' + meanpath + ' -axis 3', show=False)
    errpath = 'err_b' + str(bval) + '.mif'
    run.command('mrcalc ' + meanpath + ' -finite ' + meanpath + ' 0 -if 0 -le ' + errpath + ' -datatype bit', show=False)
    errcmd += ' ' + errpath
    if ibv>0:
      errcmd += ' -add'
      sdmpath = 'sdm_b' + str(bval) + '.mif'
      run.command('mrcalc ' + zeropath + ' ' + meanpath +  ' -divide -log ' + sdmpath, show=False)
      totvolumes += bvolumes[ibv]
      fullsdmcmd += ' ' + sdmpath + ' ' + str(bvolumes[ibv]) + ' -mult'
      if ibv>1:
        fullsdmcmd += ' -add'
  fullsdmcmd += ' ' + str(totvolumes) + ' -divide full_sdm.mif'
  run.command(fullsdmcmd, show=False)
  app.console('* Removing erroneous voxels from mask and correcting SDM...')
  run.command('mrcalc full_sdm.mif -finite full_sdm.mif 0 -if 0 -le err_sdm.mif -datatype bit', show=False)
  errcmd += ' err_sdm.mif -add 0 eroded_mask.mif -if safe_mask.mif -datatype bit'
  run.command(errcmd, show=False)
  run.command('mrcalc safe_mask.mif full_sdm.mif 0 -if 10 -min safe_sdm.mif', show=False)
  statsmaskcount = image.statistic('safe_mask.mif', 'count', '-mask safe_mask.mif')
  app.console('  [ mask: ' + str(statemaskcount) + ' -> ' + str(statsmaskcount) + ' ]')


  # CRUDE SEGMENTATION
  app.console('-------')
  app.console('Crude segmentation:')

  # Compute FA and principal eigenvectors; crude WM versus GM-CSF separation based on FA.
  app.console('* Crude WM versus GM-CSF separation (at FA=' + str(app.ARGS.fa) + ')...')
  run.command('dwi2tensor dwi.mif - -mask safe_mask.mif | tensor2metric - -fa safe_fa.mif -vector safe_vecs.mif -modulate none -mask safe_mask.mif', show=False)
  run.command('mrcalc safe_mask.mif safe_fa.mif 0 -if ' + str(app.ARGS.fa) + ' -gt crude_wm.mif -datatype bit', show=False)
  run.command('mrcalc crude_wm.mif 0 safe_mask.mif -if _crudenonwm.mif -datatype bit', show=False)
  statcrudewmcount = image.statistic('crude_wm.mif', 'count', '-mask crude_wm.mif')
  statcrudenonwmcount = image.statistic('_crudenonwm.mif', 'count', '-mask _crudenonwm.mif')
  app.console('  [ ' + str(statsmaskcount) + ' -> ' + str(statcrudewmcount) + ' (WM) & ' + str(statcrudenonwmcount) + ' (GM-CSF) ]')

  # Crude GM versus CSF separation based on SDM.
  app.console('* Crude GM versus CSF separation...')
  crudenonwmmedian = image.statistic('safe_sdm.mif', 'median', '-mask _crudenonwm.mif')
  run.command('mrcalc _crudenonwm.mif safe_sdm.mif ' + str(crudenonwmmedian) + ' -subtract 0 -if - | mrthreshold - - -mask _crudenonwm.mif | mrcalc _crudenonwm.mif - 0 -if crude_csf.mif -datatype bit', show=False)
  run.command('mrcalc crude_csf.mif 0 _crudenonwm.mif -if crude_gm.mif -datatype bit', show=False)
  statcrudegmcount = image.statistic('crude_gm.mif', 'count', '-mask crude_gm.mif')
  statcrudecsfcount = image.statistic('crude_csf.mif', 'count', '-mask crude_csf.mif')
  app.console('  [ ' + str(statcrudenonwmcount) + ' -> ' + str(statcrudegmcount) + ' (GM) & ' + str(statcrudecsfcount) + ' (CSF) ]')


  # REFINED SEGMENTATION
  app.console('-------')
  app.console('Refined segmentation:')

  # Refine WM: remove high SDM outliers.
  app.console('* Refining WM...')
  crudewmmedian = image.statistic('safe_sdm.mif', 'median', '-mask crude_wm.mif')
  run.command('mrcalc crude_wm.mif safe_sdm.mif ' + str(crudewmmedian) + ' -subtract -abs 0 -if _crudewm_sdmad.mif', show=False)
  crudewmmad = image.statistic('_crudewm_sdmad.mif', 'median', '-mask crude_wm.mif')
  crudewmoutlthresh = crudewmmedian + (1.4826 * crudewmmad * 2.0)
  run.command('mrcalc crude_wm.mif safe_sdm.mif 0 -if ' + str(crudewmoutlthresh) + ' -gt _crudewmoutliers.mif -datatype bit', show=False)
  run.command('mrcalc _crudewmoutliers.mif 0 crude_wm.mif -if refined_wm.mif -datatype bit', show=False)
  statrefwmcount = image.statistic('refined_wm.mif', 'count', '-mask refined_wm.mif')
  app.console('  [ WM: ' + str(statcrudewmcount) + ' -> ' + str(statrefwmcount) + ' ]')

  # Refine GM: separate safer GM from partial volumed voxels.
  app.console('* Refining GM...')
  crudegmmedian = image.statistic('safe_sdm.mif', 'median', '-mask crude_gm.mif')
  run.command('mrcalc crude_gm.mif safe_sdm.mif 0 -if ' + str(crudegmmedian) + ' -gt _crudegmhigh.mif -datatype bit', show=False)
  run.command('mrcalc _crudegmhigh.mif 0 crude_gm.mif -if _crudegmlow.mif -datatype bit', show=False)
  run.command('mrcalc _crudegmhigh.mif safe_sdm.mif ' + str(crudegmmedian) + ' -subtract 0 -if - | mrthreshold - - -mask _crudegmhigh.mif -invert | mrcalc _crudegmhigh.mif - 0 -if _crudegmhighselect.mif -datatype bit', show=False)
  run.command('mrcalc _crudegmlow.mif safe_sdm.mif ' + str(crudegmmedian) + ' -subtract -neg 0 -if - | mrthreshold - - -mask _crudegmlow.mif -invert | mrcalc _crudegmlow.mif - 0 -if _crudegmlowselect.mif -datatype bit', show=False)
  run.command('mrcalc _crudegmhighselect.mif 1 _crudegmlowselect.mif -if refined_gm.mif -datatype bit', show=False)
  statrefgmcount = image.statistic('refined_gm.mif', 'count', '-mask refined_gm.mif')
  app.console('  [ GM: ' + str(statcrudegmcount) + ' -> ' + str(statrefgmcount) + ' ]')

  # Refine CSF: recover lost CSF from crude WM SDM outliers, separate safer CSF from partial volumed voxels.
  app.console('* Refining CSF...')
  crudecsfmin = image.statistic('safe_sdm.mif', 'min', '-mask crude_csf.mif')
  run.command('mrcalc _crudewmoutliers.mif safe_sdm.mif 0 -if ' + str(crudecsfmin) + ' -gt 1 crude_csf.mif -if _crudecsfextra.mif -datatype bit', show=False)
  run.command('mrcalc _crudecsfextra.mif safe_sdm.mif ' + str(crudecsfmin) + ' -subtract 0 -if - | mrthreshold - - -mask _crudecsfextra.mif | mrcalc _crudecsfextra.mif - 0 -if refined_csf.mif -datatype bit', show=False)
  statrefcsfcount = image.statistic('refined_csf.mif', 'count', '-mask refined_csf.mif')
  app.console('  [ CSF: ' + str(statcrudecsfcount) + ' -> ' + str(statrefcsfcount) + ' ]')


  # FINAL VOXEL SELECTION AND RESPONSE FUNCTION ESTIMATION
  app.console('-------')
  app.console('Final voxel selection and response function estimation:')

  # Get final voxels for CSF response function estimation from refined CSF.
  app.console('* CSF:')
  app.console(' * Selecting final voxels (' + str(app.ARGS.csf) + '% of refined CSF)...')
  voxcsfcount = int(round(statrefcsfcount * app.ARGS.csf / 100.0))
  run.command('mrcalc refined_csf.mif safe_sdm.mif 0 -if - | mrthreshold - - -top ' + str(voxcsfcount) + ' -ignorezero | mrcalc refined_csf.mif - 0 -if - -datatype bit | mrconvert - voxels_csf.mif -axes 0,1,2', show=False)
  statvoxcsfcount = image.statistic('voxels_csf.mif', 'count', '-mask voxels_csf.mif')
  app.console('   [ CSF: ' + str(statrefcsfcount) + ' -> ' + str(statvoxcsfcount) + ' ]')
  # Estimate CSF response function
  app.console(' * Estimating response function...')
  run.command('amp2response dwi.mif voxels_csf.mif safe_vecs.mif response_csf.txt' + bvalues_option + ' -isotropic', show=False)

  # Get final voxels for GM response function estimation from refined GM.
  app.console('* GM:')
  app.console(' * Selecting final voxels (' + str(app.ARGS.gm) + '% of refined GM)...')
  voxgmcount = int(round(statrefgmcount * app.ARGS.gm / 100.0))
  refgmmedian = image.statistic('safe_sdm.mif', 'median', '-mask refined_gm.mif')
  run.command('mrcalc refined_gm.mif safe_sdm.mif ' + str(refgmmedian) + ' -subtract -abs 1 -add 0 -if - | mrthreshold - - -bottom ' + str(voxgmcount) + ' -ignorezero | mrcalc refined_gm.mif - 0 -if - -datatype bit | mrconvert - voxels_gm.mif -axes 0,1,2', show=False)
  statvoxgmcount = image.statistic('voxels_gm.mif', 'count', '-mask voxels_gm.mif')
  app.console('   [ GM: ' + str(statrefgmcount) + ' -> ' + str(statvoxgmcount) + ' ]')
  # Estimate GM response function
  app.console(' * Estimating response function...')
  run.command('amp2response dwi.mif voxels_gm.mif safe_vecs.mif response_gm.txt' + bvalues_option + ' -isotropic', show=False)

  # Get final voxels for single-fibre WM response function estimation from WM using TOURNIER algorithm.
  app.console('* single-fibre WM:')
  app.console(' * Selecting final voxels (' + str(app.ARGS.sfwm) + '% of refined WM)...')
  voxsfwmcount = int(round(statrefwmcount * app.ARGS.sfwm / 100.0))
  app.console('   Running TOURNIER algorithm to select ' + str(voxsfwmcount) + ' single-fibre WM voxels.')
  cleanopt = ''
  if not app.DO_CLEANUP:
    cleanopt = ' -nocleanup'
  run.command('dwi2response tournier dwi.mif _respsfwmss.txt -sf_voxels ' + str(voxsfwmcount) + ' -iter_voxels ' + str(voxsfwmcount * 10) + ' -mask refined_wm.mif -voxels voxels_sfwm.mif -scratch ' + path.quote(app.SCRATCH_DIR) + cleanopt, show=False)
  statvoxsfwmcount = image.statistic('voxels_sfwm.mif', 'count', '-mask voxels_sfwm.mif')
  app.console('   [ WM: ' + str(statrefwmcount) + ' -> ' + str(statvoxsfwmcount) + ' (single-fibre by TOURNIER algorithm) ]')
  # Estimate SF WM response function
  app.console(' * Estimating response function...')
  run.command('amp2response dwi.mif voxels_sfwm.mif safe_vecs.mif response_sfwm.txt' + bvalues_option + sfwm_lmax_option, show=False)


  # OUTPUT AND SUMMARY
  app.console('-------')
  app.console('Generating outputs...')

  # Generate 4D binary images with voxel selections at major stages in algorithm (RGB: WM=blue, GM=green, CSF=red).
  run.command('mrcat crude_csf.mif crude_gm.mif crude_wm.mif check_crude.mif -axis 3', show=False)
  run.command('mrcat refined_csf.mif refined_gm.mif refined_wm.mif check_refined.mif -axis 3', show=False)
  run.command('mrcat voxels_csf.mif voxels_gm.mif voxels_sfwm.mif check_voxels.mif -axis 3', show=False)

  # Save results to output files
  bvalhdr = { 'b-values' : ','.join(map(str,bvalues)) }
  matrix.save_matrix(path.from_user(app.ARGS.out_sfwm, False), matrix.load_matrix('response_sfwm.txt'), header=bvalhdr, fmt='%.15g', footer={})
  matrix.save_matrix(path.from_user(app.ARGS.out_gm, False), matrix.load_matrix('response_gm.txt'), header=bvalhdr, fmt='%.15g', footer={})
  matrix.save_matrix(path.from_user(app.ARGS.out_csf, False), matrix.load_matrix('response_csf.txt'), header=bvalhdr, fmt='%.15g', footer={})
  if app.ARGS.voxels:
    run.command('mrconvert check_voxels.mif ' + path.from_user(app.ARGS.voxels), mrconvert_keyval=path.from_user(app.ARGS.input), force=app.FORCE_OVERWRITE, show=False)
  app.console('-------')
