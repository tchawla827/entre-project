# README

## Project
Digital Twin of Indian Fisheries Export Cold Chain for Spoilage Risk Prediction

## Student
Tavish Chawla (IIT2023150)

## Dataset Name
DaFiF: Dataset for Fish's Freshness Problems

## Source / Link
- Dataset (Mendeley Data): https://data.mendeley.com/datasets/vx4ptwk3pb/1
- DOI: 10.17632/vx4ptwk3pb.1
- Related published paper (Data in Brief, Elsevier, open access): https://www.sciencedirect.com/science/article/pii/S2352340924009788

## Original Data Owner
Faculty of Marine Science and Fisheries, Universitas Udayana, Bali, Indonesia.
The work was funded by the Indonesian National Research and Innovation Agency (BRIN) and the Education Fund Management Institute (LPDP) under the Ministry of Finance, Indonesia.

## Authors of the Dataset
Eko Prasetyo, Nanik Suciati, Ni Putu Sutramiani, Adiananda Adiananda, Ayu Putu Wiweka Krisna Dewi.

## Time Period Covered
The fish freshness experiment was carried out over 11 days, from 19 to 29 January 2024, between 09:00 and 15:00 each day. The dataset itself was published in December 2024.

## Number of Observations
- Sensor data: 9,041 readings from the MQ135 gas sensor and 9,041 readings from the TGS2602 gas sensor, for each of the 3 fish species. This gives about 18,082 sensor readings per species, and around 54,246 sensor readings in total across all three species.
- Image data: 859 images of mackerel, 840 images of tilapia, and 837 images of tuna (2,536 images in total).
- Organoleptic data: freshness scores recorded once a day for 11 days, using 6 quality parameters, for each species.

## Variables Included
1. Fish species: mackerel, tilapia, tuna
2. Day of storage (Day 1 to Day 11)
3. Session number (each day has 1 or 2 sessions)
4. MQ135 sensor reading (gas value related to ammonia released by the fish)
5. TGS2602 sensor reading (gas value related to spoilage odor)
6. Fish images (photos taken at each session, used for visual freshness checking)
7. Organoleptic freshness scores across 6 parameters, based on the Indonesian National Standard (SNI 2729-2013):
   - Eyes
   - Gills
   - Body surface mucus
   - Meat
   - Smell
   - Body texture
   (Each parameter is scored from 1 to 9, where 9 means very fresh and 1 means spoiled.)

## Why This Dataset Was Chosen
This project aims to build a digital twin of the fisheries export cold chain and predict spoilage risk using a Gradient Boosting classifier. To train such a classifier, real data showing how fish freshness changes over time under storage is needed as the ground truth label for "spoiled" versus "not spoiled."

The DaFiF dataset gives exactly this kind of data. It records how gas sensor readings change as fish loses freshness while stored on ice, and pairs each sensor reading with an expert freshness score. This makes it possible to:
- Train a model that learns the relationship between sensor readings (similar to what an IoT temperature/gas sensor in a real cold chain would record) and spoilage risk.
- Use the organoleptic scores as class labels for the spoilage classifier (for example, grouping scores into "fresh," "moderately fresh," and "spoiled" categories).
- Feed model outputs into the digital twin simulation as the spoilage-risk function, which can then be tested against different simulated transport conditions (time delay, temperature exposure, handling frequency).

This dataset was selected instead of an outdated or unrelated dataset because it is recent (published in 2024), was generated in a controlled and well-documented lab setting, and comes from a verifiable academic source (Universitas Udayana) with peer review through Elsevier's Data in Brief journal. It is also different from the datasets chosen by teammates working on related cold chain projects, since it is raw sensor and organoleptic data, not trade statistics or regulatory rejection records.

## Format
CSV files for sensor data and organoleptic scores, JPG image files for the photographs. All files can be downloaded directly from the Mendeley Data link above.

## License
CC BY 4.0 (Creative Commons Attribution), as stated on the Mendeley Data page. Free to use with attribution to the original authors.