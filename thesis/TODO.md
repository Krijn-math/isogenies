# To do (page)

- Names are still placed straight above each other where there is room to put them side by side, e.g.
  Robi Pedersen / Jorge Chávez-Saab, Maria Corte-Real Santos / Fabio Felipe Campos, Pierrick Dartois / Marc Houben.
  Likely causes in `assets/forest.js`: `settle()` stacking names vertically when that is cheaper (`SPREAD_COST`),
  and `declutter()` choosing a height within the year (`dys`) without any cost for sitting right above or below
  another name. Prefer side by side whenever the width allows.
