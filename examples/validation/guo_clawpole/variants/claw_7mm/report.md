# Guo et al. 2003-2007, 3-phase SMC claw-pole motor, 500 W at 1800 rpm (Table V of the TFM paper): claw_7mm

Y. G. Guo, J. G. Zhu, P. A. Watterson, W. Wu, "Development of a permanent magnet claw pole motor with soft magnetic composite core", Australian J. Electrical & Electronics Eng. 2(1), 21-30, 2005 (main paper, open: https://opus.lib.uts.edu.au/bitstream/10453/166879/3/). Also: Guo, Zhu, Lu, IEE Proc. EPA 153(4), 2006; Guo, Zhu, Wu, JSAEM 15, 2005 (2nd sub-airgap); Guo, Zhu, Wu, IEEE TMAG 41(6), 2005 (wire); Guo, Zhu, Zhong, Wu, IEEE TMAG 39(5), 2003 (SOMALOY 500 loss fit).

118036 elements per sector, 24 positions per electrical period, 1061 s.

| Quantity | Published | Kind | Computed | Difference |
|---|---|---|---|---|
| Back-EMF constant (measured 68 V peak at 1800 rpm) | 0.2552 V s | measured (read from figure) | 0.2867 V s | +12.4 % |
| Back-EMF constant Ke, authors' FEA | 0.2594 V s | FEA | 0.2867 V s | +10.5 % |
| No-load flux per turn, fundamental | 0.48 mWb | FEA | 0.5407 mWb | +12.6 % |
| Cogging torque, one stack, peak | 0.75 N m | FEA (read from figure) | 1.19 N m | +58.7 % |
| Cogging torque, three stacks, peak | 0.33 N m | measured (read from figure) | 0.4653 N m | +41.0 % |
| Cogging torque, three stacks, authors' FEA (6th harmonic) | 0.381 N m | FEA | 0.4653 N m | +22.1 % |
| Phase inductance | 5.79 mH | measured | 7.411 mH | +28.0 % |
| Phase inductance, authors' FEA (0.932 uH per turn) | 5.24 mH | FEA | 7.411 mH | +41.4 % |
| Phase resistance at room temperature | 0.225 ohm | measured | 0.261 ohm | +16.0 % |
| Electromagnetic torque at 4.1 A (601.5 W / 188.5 rad/s) | 3.19 N m | authors' calculation | 3.378 N m | +5.9 % |
| Core loss, no load, 1800 rpm | 60 W | measured (read from figure) | 34.95 W | -41.8 % |
| Core loss, no load, 1800 rpm, authors' FEA | 58 W | FEA (rotational-loss model) | 34.95 W | -39.7 % |
| Output torque at 1800 rpm (rated) | 2.65 N m | measured | 3.161 N m | +19.3 % |
| Efficiency at rated torque (drive total, includes the inverter) | 0.81  | measured | 0.9116  | +12.5 % |

Kind: measured on the prototype, FEA of the authors, or derived from published values.
