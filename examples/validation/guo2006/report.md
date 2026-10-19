# Guo et al. 2006, 3-phase SMC TFM, 640 W at 1800 rpm (review Table 2, row 5): base

Y. G. Guo, J. G. Zhu, P. A. Watterson, W. Wu, "Development of a PM transverse flux motor with soft magnetic composite core", IEEE Trans. Energy Conversion 21(2), 426-434, 2006. Open copy: https://opus.lib.uts.edu.au/bitstream/10453/5857/3/2006004024.pdf. Design paper: Guo et al., ICEMS 2003.

121492 elements per sector, 24 positions per electrical period, 733 s.

| Quantity | Published | Kind | Computed | Difference |
|---|---|---|---|---|
| Back-EMF constant k (E1 rms = k * omega) | 0.244 V s | measured | 0.2789 V s | +14.3 % |
| Back-EMF constant k, authors' FEA | 0.247 V s | FEA | 0.2789 V s | +12.9 % |
| No-load flux per turn, peak (Fig. 4) | 0.28 mWb | FEA (read from figure) | 0.3171 mWb | +13.2 % |
| Cogging torque, one stack, peak (Fig. 5) | 1.07 N m | FEA (read from figure) | 0.3991 N m | -62.7 % |
| Cogging torque, three stacks, peak | 0.32 N m | measured | 0.3165 N m | -1.1 % |
| Cogging torque, three stacks, authors' FEA | 0.339 N m | FEA | 0.3165 N m | -6.6 % |
| Phase inductance (mean of 6.33 / 6.94 / 6.33) | 6.53 mH | measured | 7.407 mH | +13.4 % |
| Phase inductance, authors' FEA | 6.68 mH | FEA | 7.407 mH | +10.9 % |
| Phase resistance at 20 C | 0.305 ohm | measured | 0.3275 ohm | +7.4 % |
| Electromagnetic torque at 5.5 A (3 k I) | 4.03 N m | derived from measured k and I | 4.544 N m | +12.8 % |
| Stator SMC core loss, no load, 1800 rpm | 29 W | FEA (authors, rotational model, TMAG 2014) | 21.01 W | -27.6 % |
| Rotor yoke loss, no load, 1800 rpm | 34.3 W | authors' calculation (TMAG 2014, fitted k_e) | 24.79 W | -27.7 % |
| Core loss, no load, 1800 rpm (stator + rotor) | 68.2 W | measured (TMAG 2014; 69 W in TEC 2006) | 45.8 W | -32.8 % |
| Stator SMC core loss, rated load | 56.5 W | FEA (authors, TMAG 2014) | 34.59 W | -38.8 % |
| Rotor yoke loss, rated load | 63.8 W | authors' calculation (TMAG 2014) | 59.86 W | -6.2 % |
| Core loss, rated load (stator + rotor) | 112 W | measured (TEC 2006; 131.2 W derived in TMAG 2014) | 94.45 W | -15.7 % |
| Output torque at 1800 rpm, 5.5 A | 3.4 N m | measured | 4.011 N m | +18.0 % |
| Motor efficiency (640 / (805 - 11 inverter)) | 0.806  | derived from measured powers | 0.8458  | +4.9 % |

Kind: measured on the prototype, FEA of the authors, or derived from published values.
