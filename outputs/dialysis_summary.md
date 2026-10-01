# Dialysis-clinic visibility in Overture (scored tracts, 5 regions)

Facilities inside scored tracts: 863  (geocoder: {'census': 795, 'nominatim': 68})

## Status overall
| status           |   count |
|:-----------------|--------:|
| mapped_dialysis  |     728 |
| missing          |      92 |
| mapped_other_cat |      43 |

## By region
| region           |   n |   unseen_rate |   missing_rate |   stations |
|:-----------------|----:|--------------:|---------------:|-----------:|
| eastern-ok       |  75 |         0.12  |          0.107 |       1209 |
| eastern-wa       |  27 |         0.037 |          0.037 |        398 |
| maricopa-az      | 103 |         0.087 |          0.049 |       1928 |
| northern-ca      |  38 |         0.079 |          0.079 |        751 |
| south-central-tx | 620 |         0.182 |          0.121 |      11847 |

## By rural
|   rural |   n |   unseen_rate |   missing_rate |   stations |
|--------:|----:|--------------:|---------------:|-----------:|
|       0 | 731 |         0.157 |          0.108 |      13958 |
|       1 | 132 |         0.152 |          0.098 |       2175 |

## By svi_q
| svi_q      |   n |   unseen_rate |   missing_rate |   stations |
|:-----------|----:|--------------:|---------------:|-----------:|
| Q1 (least) | 216 |         0.134 |          0.102 |       3547 |
| Q2         | 215 |         0.177 |          0.121 |       3994 |
| Q3         | 215 |         0.149 |          0.107 |       4083 |
| Q4 (most)  | 215 |         0.158 |          0.098 |       4474 |

## By tribal
|   tribal |   n |   unseen_rate |   missing_rate |   stations |
|---------:|----:|--------------:|---------------:|-----------:|
|        0 | 810 |         0.16  |          0.109 |      15243 |
|        1 |  53 |         0.094 |          0.075 |        890 |

## By chain
|   chain |   n |   unseen_rate |   missing_rate |   stations |
|--------:|----:|--------------:|---------------:|-----------:|
|       0 |  44 |         0.5   |          0.227 |        482 |
|       1 | 819 |         0.138 |          0.1   |      15651 |

## By nonprofit
|   nonprofit |   n |   unseen_rate |   missing_rate |   stations |
|------------:|----:|--------------:|---------------:|-----------:|
|           0 | 824 |         0.149 |          0.107 |      15495 |
|           1 |  39 |         0.308 |          0.103 |        638 |

## By hospital_based
|   hospital_based |   n |   unseen_rate |   missing_rate |   stations |
|-----------------:|----:|--------------:|---------------:|-----------:|
|                0 | 765 |         0.149 |          0.107 |      14227 |
|                1 |  98 |         0.214 |          0.102 |       1906 |

## By pediatric
|   pediatric |   n |   unseen_rate |   missing_rate |   stations |
|------------:|----:|--------------:|---------------:|-----------:|
|           0 | 851 |         0.149 |          0.106 |      16043 |
|           1 |  12 |         0.667 |          0.167 |         90 |

## By geocoder
| geocoder   |   n |   unseen_rate |   missing_rate |   stations |
|:-----------|----:|--------------:|---------------:|-----------:|
| census     | 795 |         0.132 |          0.089 |      14925 |
| nominatim  |  68 |         0.441 |          0.309 |       1208 |

## Tests
| contrast       | test                  |   stat (OR or rho) |           p |
|:---------------|:----------------------|-------------------:|------------:|
| rural          | Fisher exact (unseen) |              0.957 | 1           |
| tribal         | Fisher exact (unseen) |              0.545 | 0.243828    |
| chain          | Fisher exact (unseen) |              0.16  | 4.00541e-08 |
| nonprofit      | Fisher exact (unseen) |              2.533 | 0.0126193   |
| hospital_based | Fisher exact (unseen) |              1.557 | 0.104003    |
| pediatric      | Fisher exact (unseen) |             11.402 | 8.43138e-05 |
| SVI Q1 vs Q4   | Fisher exact (unseen) |              1.211 | 0.49853     |
| svi_overall    | Spearman vs unseen    |              0.011 | 0.74327     |

## Robustness: Census-geocoded facilities only
|   hospital_based |   n |   unseen |   misfiled |
|-----------------:|----:|---------:|-----------:|
|                0 | 705 |    0.122 |      0.034 |
|                1 |  90 |    0.211 |      0.111 |

## Pediatric x hospital-based
|        |   n |   unseen |   misfiled |   stations |
|:-------|----:|---------:|-----------:|-----------:|
| (0, 0) | 762 |    0.15  |      0.042 |      14208 |
| (0, 1) |  89 |    0.146 |      0.056 |       1835 |
| (1, 0) |   3 |    0     |      0     |         19 |
| (1, 1) |   9 |    0.889 |      0.667 |         71 |

## Every pediatric dialysis unit in the scored tracts
| Facility Name                                      | City/Town      | State   | region           |       GEOID | status           | matched_cat                                                          |   stations |   next_mapped_dialysis_km |   nearest_visible_pediatric_km |
|:---------------------------------------------------|:---------------|:--------|:-----------------|------------:|:-----------------|:---------------------------------------------------------------------|-----------:|--------------------------:|-------------------------------:|
| 032314 PHOENIX CHILDRENS HOSPITAL- DIALYSIS CENTER | PHOENIX        | AZ      | maricopa-az      | 04013111602 | mapped_other_cat | hospital                                                             |          6 |                  1.83045  |                      1016.66   |
| UC Davis Medical Center Pediatric                  | SACRAMENTO     | CA      | northern-ca      | 06067001702 | mapped_dialysis  | dialysis_clinic;nephrologist                                         |          1 |                  1.54924  |                      2338.38   |
| CHILDREN'S MEMORIAL HERMANN DIALYSIS CENTER        | HOUSTON        | TX      | south-central-tx | 48201313102 | mapped_other_cat | medical_center                                                       |          7 |                  1.17303  |                       232.007  |
| TEXAS CHILDRENS HOSPITAL DIALYSIS UNIT             | HOUSTON        | TX      | south-central-tx | 48201313102 | mapped_other_cat | gastroenterologist;health_and_medical;medical_center                 |         13 |                  0.85255  |                       231.758  |
| CHILDRENS MEDICAL CENTER DIALYSIS UNIT             | DALLAS         | TX      | south-central-tx | 48113010001 | mapped_other_cat | pediatric_nephrology;pediatrician                                    |         19 |                  1.57535  |                       290.318  |
| COOK CHILDRENS MEDICAL CENTER DIALYSIS UNIT        | FORT WORTH     | TX      | south-central-tx | 48439123700 | mapped_other_cat | health_and_medical;nephrologist                                      |          8 |                  0.692153 |                       272.703  |
| CHRISTUS CHILDRENS KIDNEY CENTER                   | SAN ANTONIO    | TX      | south-central-tx | 48029110100 | mapped_dialysis  | dialysis_clinic;health_and_medical;nephrologist                      |          8 |                  0.262259 |                       123.82   |
| DRISCOLL CHILDREN'S HOSPITAL DIALYSIS UNIT         | CORPUS CHRISTI | TX      | south-central-tx | 48355002101 | missing          |                                                                      |          5 |                  2.21658  |                       192.263  |
| UNIVERSITY HEALTH SYSTEM CHILDREN'S KIDNEY CENTER  | SAN ANTONIO    | TX      | south-central-tx | 48029181402 | mapped_other_cat | diagnostic_services;medical_center;nephrologist;pediatric_nephrology |          8 |                  0.473829 |                        11.6318 |
| Texas Children's Hospital North Austin Campus      | Austin         | TX      | south-central-tx | 48491020311 | missing          |                                                                      |          4 |                  6.01102  |                        20.527  |
| CHILDRENS DIALYSIS CLINIC OF CENTRAL TEXAS         | AUSTIN         | TX      | south-central-tx | 48453000309 | mapped_dialysis  | dermatologist;dialysis_clinic;hospital                               |          7 |                  0.913597 |                       123.82   |
| DRISCOLL CHILDREN'S VALLEY DIALYSIS CENTER         | MCALLEN        | TX      | south-central-tx | 48215021204 | mapped_dialysis  | dialysis_clinic;health_and_medical                                   |          4 |                  0.301356 |                       361.84   |

## Logit: unseen ~ rural + SVI + tribal + chain + region FE
```
                                Coef.  Std.Err.       z   P>|z|  [0.025  0.975]
Intercept                     -0.5683    0.5905 -0.9625  0.3358 -1.7256  0.5890
C(region)[T.eastern-wa]       -1.1029    1.1395 -0.9679  0.3331 -3.3363  1.1305
C(region)[T.maricopa-az]      -0.5341    0.6268 -0.8521  0.3942 -1.7625  0.6944
C(region)[T.northern-ca]      -0.3777    0.7850 -0.4811  0.6305 -1.9163  1.1610
C(region)[T.south-central-tx]  0.5176    0.5234  0.9889  0.3227 -0.5083  1.5435
rural                          0.0579    0.2916  0.1986  0.8426 -0.5136  0.6295
svi_overall                    0.2564    0.3746  0.6846  0.4936 -0.4777  0.9906
tribal                        -0.3219    0.6803 -0.4732  0.6360 -1.6553  1.0114
chain                         -1.7904    0.3324 -5.3869  0.0000 -2.4419 -1.1390
hospital_based                 0.2157    0.2926  0.7372  0.4610 -0.3577  0.7891
```

## Consequence
Unseen facilities: 135, stations 2082. Median distance from an unseen clinic to the next clinic a category search returns: 1.1 km (rural: 2.2 km).
