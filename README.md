## These codes are the core scripts for creating the TP MWH dataset used in the article "Landsat-Derived Gap-Free Monthly 30-m Dataset (2000–2021) Unraveling Intra-Annual Surface Water Dynamics on the Tibetan Plateaud". 

#It can be used for downloading and reconstructing the original JRC MWH dataset on the Google Earth Engine and Python.

#1---GEE_download_JRCMWH_code.txt
Open this file in the Google Earth Engine Code Editor. It includes image collection filtering and image clipping functions and is used to download the initial dataset used in the article.

#2---SGFmethod_step12.py
Open this file in Python. It reads the initial dataset downloaded locally and reconstructs the dataset using the stepwise gap-filling method for step_1 & 2.

#3---SGFmethod_step34.py
Open this file in Python. It reads the dataset saved locally after step_1 & 2 reconstruction and performs step_3 & 4 reconstruction using the stepwise gap-filling method. The reconstructed dataset is the final version used in the article.

#The dataset is saved in TIFF format, which can be opened and visualized in QGIS software.
