# EDA — electricity retail packages

Rows: 26  |  sellers: 5  |  collected: 2026-10-03T17:14:12+00:00

## Offers by seller and package type
```
package_type     bundle  exchange  fixed  hybrid
seller                                          
Altra Energy          1         4      3       1
Elm Energy            0         1      1       0
Solarix               0         4      0       0
Terminal Energy       0         2      8       0
VoltEdge              0         1      0       0
```

## Fixed-package energy price, c/kWh (incl. VAT where stated)
```
count    12.000000
mean     13.854917
std       2.627607
min       9.796000
25%      12.095250
50%      13.850000
75%      15.451500
max      17.900000
```

## Exchange-package margin over spot, c/kWh
```
count    12.000000
mean      0.307000
std       0.288499
min       0.000000
25%       0.000000
50%       0.400000
75%       0.487500
max       0.744000
```

## Monthly fee, EUR
```
count    24.000000
mean      4.112500
std       5.368476
min       0.000000
25%       1.910000
50%       1.955000
75%       3.250000
max      24.000000
```

## Mean cost by seller
```
                              count    mean     min     max
seller          package_type                               
Altra Energy    bundle            1  15.500  15.500  15.500
                exchange          4   0.332   0.000   0.470
                fixed             3  15.200  13.400  17.900
                hybrid            1  15.900  15.900  15.900
Elm Energy      exchange          1   0.670   0.670   0.670
                fixed             1  13.220  13.220  13.220
Solarix         exchange          4   0.000   0.000   0.000
Terminal Energy exchange          2   0.642   0.540   0.744
                fixed             8  13.430   9.796  16.918
VoltEdge        exchange          1   0.400   0.400   0.400
```

## Fixed-price term structure (Terminal Energy, c/kWh by months)
```
 period_months  cost_per_kwh_c  green
           3.0           9.920   True
           3.0           9.796  False
           6.0          16.918   True
           6.0          16.794  False
          12.0          15.004   True
          12.0          14.880  False
          36.0          12.127   True
          36.0          12.000  False
```

## Text statistics
```
       desc_len_chars  desc_len_words
count       26.000000       26.000000
mean       410.615385       68.615385
std        263.098320       48.901597
min        210.000000       32.000000
25%        264.750000       40.750000
50%        293.000000       48.000000
75%        378.000000       61.750000
max        939.000000      171.000000
```

Total tokens: 1125  |  vocabulary: 162  |  tokens/row: 43

## Top-25 words (stopwords removed)
```
price                 97 #################################################################################################
kwh                   81 #################################################################################
margin                69 #####################################################################
fee                   48 ################################################
monthly               43 ###########################################
months                36 ####################################
exchange              33 #################################
consumption           32 ################################
electricity           27 ###########################
buyback               23 #######################
fixed                 22 ######################
package               22 ######################
tariff                21 #####################
contract              18 ##################
open                  16 ################
ended                 16 ################
term                  15 ###############
every                 13 #############
vat                   13 #############
steer                 11 ###########
single                11 ###########
dual                  11 ###########
applies               11 ###########
joint                 10 ##########
invoice               10 ##########
```

## Top-12 words per package type
```
bundle     volume(6), kwh(4), monthly(3), fee(3), fixed(2), joint(2), invoice(2), gridco(2), network(2), services(2), above(2), consumption(2)
exchange   kwh(60), margin(52), price(42), fee(32), exchange(30), monthly(28), electricity(23), consumption(19), package(16), open(15), ended(15), buyback(15)
fixed      price(51), months(27), tariff(21), fixed(16), margin(16), kwh(15), fee(12), monthly(11), consumption(11), single(11), dual(11), applies(11)
hybrid     price(2), month(2), kwh(2), stress(1), free(1), joint(1), invoice(1), gridco(1), network(1), services(1), fixed(1), lower(1)
```

Pearson r (description length vs cost): -0.386

