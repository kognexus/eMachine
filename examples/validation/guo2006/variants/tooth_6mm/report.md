# Guo et al. 2006, 3-phase SMC TFM, 640 W at 1800 rpm (review Table 2, row 5): tooth_6mm

Y. G. Guo, J. G. Zhu, P. A. Watterson, W. Wu, "Development of a PM transverse flux motor with soft magnetic composite core", IEEE Trans. Energy Conversion 21(2), 426-434, 2006. Open copy: https://opus.lib.uts.edu.au/bitstream/10453/5857/3/2006004024.pdf. Design paper: Guo et al., ICEMS 2003.

121857 elements per sector, 24 positions per electrical period, 512 s.

| Quantity | Published | Kind | Computed | Difference |
|---|---|---|---|---|
| Back-EMF constant k (E1 rms = k * omega) | 0.244 V s | measured | 0.2614 V s | +7.1 % |
| Back-EMF constant k, authors' FEA | 0.247 V s | FEA | 0.2614 V s | +5.8 % |
| No-load flux per turn, peak (Fig. 4) | 0.28 mWb | FEA (read from figure) | 0.2975 mWb | +6.2 % |
| Cogging torque, one stack, peak (Fig. 5) | 1.07 N m | FEA (read from figure) | 0.5232 N m | -51.1 % |
| Cogging torque, three stacks, peak | 0.32 N m | measured | 0.3086 N m | -3.6 % |
| Cogging torque, three stacks, authors' FEA | 0.339 N m | FEA | 0.3086 N m | -9.0 % |
| Phase inductance (mean of 6.33 / 6.94 / 6.33) | 6.53 mH | measured | 7.752 mH | +18.7 % |
| Phase inductance, authors' FEA | 6.68 mH | FEA | 7.752 mH | +16.0 % |
| Phase resistance at 20 C | 0.305 ohm | measured | 0.3275 ohm | +7.4 % |
| Electromagnetic torque at 5.5 A (3 k I) | 4.03 N m | derived from measured k and I | 4.272 N m | +6.0 % |
| Stator SMC core loss, no load, 1800 rpm | 29 W | FEA (authors' rotating-loss model) | 14.51 W | -50.0 % |
| Output torque at 1800 rpm, 5.5 A | 3.4 N m | measured | 4.163 N m | +22.4 % |
| Motor efficiency (640 / (805 - 11 inverter)) | 0.806  | derived from measured powers | 0.9312  | +15.5 % |

Kind: measured on the prototype, FEA of the authors, or derived from published values.
