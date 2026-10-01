# Spatial-CV report
Target: PROXY = label-free structural estimate (estimate.py defaults). n=9794, groups = counties (325), GroupKFold(5).

## Model set: all_features (77 features), LightGBM params {'num_leaves': 31, 'learning_rate': 0.03, 'min_child_samples': 20, 'n_estimators': 800}

|        |    rmse |     mae |
|:-------|--------:|--------:|
| zero   | 0.07954 | 0.04808 |
| median | 0.06786 | 0.04624 |
| ridge  | 0.04782 | 0.03211 |
| lgbm   | 0.01268 | 0.00498 |

Top features (gain): poi_school_name_other_cat, poi_schools, road_km_county_lowclass, poi_fire_name_other_cat, poi_fire, road_km_named_unsigned, road_km_named, road_km_county_route, poi_ems_name_other_cat, road_km_signed, poi_ems, road_km_signed_lowclass

Error by group (LightGBM OOF):
|                         |    n |   y_mean |   pred_mean |    bias |   rmse |
|:------------------------|-----:|---------:|------------:|--------:|-------:|
| region=eastern-ok       | 1192 |   0.073  |      0.0719 | -0.0011 | 0.0198 |
| region=eastern-wa       |  415 |   0.0292 |      0.0308 |  0.0016 | 0.0092 |
| region=maricopa-az      | 1593 |   0.0414 |      0.0415 |  0      | 0.0102 |
| region=northern-ca      |  591 |   0.0358 |      0.0373 |  0.0015 | 0.0073 |
| region=south-central-tx | 6003 |   0.0474 |      0.048  |  0.0006 | 0.0121 |
| rural=rural             | 1691 |   0.0565 |      0.0566 |  0.0001 | 0.02   |
| rural=urban             | 8103 |   0.0463 |      0.0468 |  0.0004 | 0.0105 |
| tribal=non-tribal       | 8920 |   0.0457 |      0.0462 |  0.0005 | 0.0116 |
| tribal=tribal           |  874 |   0.0725 |      0.0717 | -0.0007 | 0.0207 |
| svi_q=Q1                | 2428 |   0.0479 |      0.0483 |  0.0004 | 0.0131 |
| svi_q=Q2                | 2425 |   0.0517 |      0.0515 | -0.0003 | 0.014  |
| svi_q=Q3                | 2428 |   0.051  |      0.0515 |  0.0004 | 0.0135 |
| svi_q=Q4                | 2425 |   0.0424 |      0.0432 |  0.0009 | 0.0099 |

## Model set: demographics_only (21 features), LightGBM params {'num_leaves': 15, 'learning_rate': 0.03, 'min_child_samples': 40, 'n_estimators': 600}

|        |    rmse |     mae |
|:-------|--------:|--------:|
| zero   | 0.07954 | 0.04808 |
| median | 0.06786 | 0.04624 |
| ridge  | 0.06271 | 0.04819 |
| lgbm   | 0.06271 | 0.04784 |

Top features (gain): log_density, usdm_summer_dsci, epht_heat_days_summer, svi_minority, usfs_WHP_mean, svi_housing_transport, cvi_overall, log_hu, log_pop, ghcn_any_nearest_km, usfs_RPS_mean, svi_household

Error by group (LightGBM OOF):
|                         |    n |   y_mean |   pred_mean |    bias |   rmse |
|:------------------------|-----:|---------:|------------:|--------:|-------:|
| region=eastern-ok       | 1192 |   0.073  |      0.0715 | -0.0015 | 0.0755 |
| region=eastern-wa       |  415 |   0.0292 |      0.0465 |  0.0174 | 0.0502 |
| region=maricopa-az      | 1593 |   0.0414 |      0.042  |  0.0005 | 0.064  |
| region=northern-ca      |  591 |   0.0358 |      0.0424 |  0.0066 | 0.0552 |
| region=south-central-tx | 6003 |   0.0474 |      0.0459 | -0.0015 | 0.061  |
| rural=rural             | 1691 |   0.0565 |      0.0571 |  0.0006 | 0.0649 |
| rural=urban             | 8103 |   0.0463 |      0.0463 |  0      | 0.0622 |
| tribal=non-tribal       | 8920 |   0.0457 |      0.0456 | -0.0001 | 0.0616 |
| tribal=tribal           |  874 |   0.0725 |      0.0743 |  0.0019 | 0.0733 |
| svi_q=Q1                | 2428 |   0.0479 |      0.048  |  0.0001 | 0.0661 |
| svi_q=Q2                | 2425 |   0.0517 |      0.0518 |  0.0001 | 0.0651 |
| svi_q=Q3                | 2428 |   0.051  |      0.0507 | -0.0003 | 0.0604 |
| svi_q=Q4                | 2425 |   0.0424 |      0.0427 |  0.0003 | 0.0586 |
