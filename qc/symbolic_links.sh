for subj in *; do
  if [ -d "$subj/surf" ]; then
    [ -e "$subj/surf/rh.white.H" ] || ln -s rh.white.preaparc.H "$subj/surf/rh.white.H"
    [ -e "$subj/surf/rh.white.K" ] || ln -s rh.white.preaparc.K "$subj/surf/rh.white.K"
    [ -e "$subj/surf/rh.pial" ] || ln -s rh.pial.T2 "$subj/surf/rh.pial"
    [ -e "$subj/surf/rh.fsaverage.sphere.reg" ] || ln -s rh.sphere.reg "$subj/surf/rh.fsaverage.sphere.reg"
  fi
done

