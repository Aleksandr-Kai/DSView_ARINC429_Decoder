# Decoder (ARINC 429) plugin for ![](https://www.dreamsourcelab.com/wp-content/uploads/2017/08/logo-small1.png) [DSView](https://github.com/DreamSourceLab/DSView)

For linux:
Copy pd.py to _/usr/local/share/libsigrokdecode4DSL/decoders/arinc_. And create \_\_init\_\_.py empty.

## Important

**Sigrok** api_version = 3

![example](screenshots/2023-05-16_08-45.png)

![example](screenshots/2.png)

You can configure the decoding parameters of several parameters in the config.ini (will be created in _<user_home>/arinc_plugin/_ after clicking Ok with the "Use config" option selected) configuration file and save the result in .csv files

![example](screenshots/3.png)

config.ini is located at `<user folder>/arinc_plugin/config.ini`

[on GitLab](https://gitlab.com/Aleksandr-Kai/DSView_ARINC429_Decoder) (forcing to turn on 2fa sucks. ms will kill github)
