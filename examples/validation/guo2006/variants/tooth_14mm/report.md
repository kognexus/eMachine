# Guo et al. 2006, 3-phase SMC TFM, 640 W at 1800 rpm (review Table 2, row 5): tooth_14mm

Y. G. Guo, J. G. Zhu, P. A. Watterson, W. Wu, "Development of a PM transverse flux motor with soft magnetic composite core", IEEE Trans. Energy Conversion 21(2), 426-434, 2006. Open copy: https://opus.lib.uts.edu.au/bitstream/10453/5857/3/2006004024.pdf. Design paper: Guo et al., ICEMS 2003.

121771 elements per sector, 24 positions per electrical period, 544 s.

| Quantity | Published | Kind | Computed | Difference |
|---|---|---|---|---|
| Back-EMF constant k (E1 rms = k * omega) | 0.244 V s | measured | 0.2805 V s | +15.0 % |
| Back-EMF constant k, authors' FEA | 0.247 V s | FEA | 0.2805 V s | +13.6 % |
| No-load flux per turn, peak (Fig. 4) | 0.28 mWb | FEA (read from figure) | 0.3188 mWb | +13.9 % |
| Cogging torque, one stack, peak (Fig. 5) | 1.07 N m | FEA (read from figure) | 0.3815 N m | -64.3 % |
| Cogging torque, three stacks, peak | 0.32 N m | measured | 0.3193 N m | -0.2 % |
| Cogging torque, three stacks, authors' FEA | 0.339 N m | FEA | 0.3193 N m | -5.8 % |
| Phase inductance (mean of 6.33 / 6.94 / 6.33) | 6.53 mH | measured | 7.273 mH | +11.4 % |
| Phase inductance, authors' FEA | 6.68 mH | FEA | 7.273 mH | +8.9 % |
| Phase resistance at 20 C | 0.305 ohm | measured | 0.3275 ohm | +7.4 % |
| Electromagnetic torque at 5.5 A (3 k I) | 4.03 N m | derived from measured k and I | 4.575 N m | +13.5 % |
| Stator SMC core loss, no load, 1800 rpm | 29 W | FEA (authors' rotating-loss model) | 16.02 W | -44.7 % |
| Output torque at 1800 rpm, 5.5 A | 3.4 N m | measured | 4.458 N m | +31.1 % |
| Motor efficiency (640 / (805 - 11 inverter)) | 0.806  | derived from measured powers | 0.9339  | +15.9 % |

Kind: measured on the prototype, FEA of the authors, or derived from published values.
