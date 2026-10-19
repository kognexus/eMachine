# Guo et al. 2003-2007, 3-phase SMC claw-pole motor, 500 W at 1800 rpm (Table V of the TFM paper): base

Y. G. Guo, J. G. Zhu, P. A. Watterson, W. Wu, "Development of a permanent magnet claw pole motor with soft magnetic composite core", Australian J. Electrical & Electronics Eng. 2(1), 21-30, 2005 (main paper, open: https://opus.lib.uts.edu.au/bitstream/10453/166879/3/). Also: Guo, Zhu, Lu, IEE Proc. EPA 153(4), 2006; Guo, Zhu, Wu, JSAEM 15, 2005 (2nd sub-airgap); Guo, Zhu, Wu, IEEE TMAG 41(6), 2005 (wire); Guo, Zhu, Zhong, Wu, IEEE TMAG 39(5), 2003 (SOMALOY 500 loss fit).

117319 elements per sector, 24 positions per electrical period, 1281 s.

| Quantity | Published | Kind | Computed | Difference |
|---|---|---|---|---|
| Back-EMF constant (measured 68 V peak at 1800 rpm) | 0.2552 V s | measured (read from figure) | 0.2449 V s | -4.0 % |
| Back-EMF constant Ke, authors' FEA | 0.2594 V s | FEA | 0.2449 V s | -5.6 % |
| No-load flux per turn, fundamental | 0.48 mWb | FEA | 0.4619 mWb | -3.8 % |
| Cogging torque, one stack, peak | 0.75 N m | FEA (read from figure) | 1.296 N m | +72.8 % |
| Cogging torque, three stacks, peak | 0.33 N m | measured (read from figure) | 0.4598 N m | +39.3 % |
| Cogging torque, three stacks, authors' FEA (6th harmonic) | 0.381 N m | FEA | 0.4598 N m | +20.7 % |
| Phase inductance | 5.79 mH | measured | 8.037 mH | +38.8 % |
| Phase inductance, authors' FEA (0.932 uH per turn) | 5.24 mH | FEA | 8.037 mH | +53.4 % |
| Phase resistance at room temperature | 0.225 ohm | measured | 0.2303 ohm | +2.4 % |
| Electromagnetic torque at 4.1 A (601.5 W / 188.5 rad/s) | 3.19 N m | authors' calculation | 2.794 N m | -12.4 % |
| Core loss, no load, 1800 rpm | 60 W | measured (read from figure) | 43.87 W | -26.9 % |
| Stator core loss, no load, authors' FEA (rotor loss taken as negligible) | 58 W | FEA (rotational model) | 40.4 W | -30.4 % |
| Stator core loss, full load, authors' FEA | 81.8 W | FEA (rotational model) | 66.3 W | -19.0 % |
| Output torque at 1800 rpm (rated) | 2.65 N m | measured | 2.388 N m | -9.9 % |
| Efficiency at rated torque (drive total, includes the inverter) | 0.81  | measured | 0.8312  | +2.6 % |

Kind: measured on the prototype, FEA of the authors, or derived from published values.
