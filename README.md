# Decoder (ARINC 429) plugin for ![](https://www.dreamsourcelab.com/wp-content/uploads/2017/08/logo-small1.png) [DSView](https://github.com/DreamSourceLab/DSView)
> Sigrok API version 3

For linux:
- Copy `pd.py` to `/usr/local/share/libsigrokdecode4DSL/decoders/arinc429`.
- Create `__init__.py` empty.

![example](screenshots/2023-05-16_08-45.png)

---

![example](screenshots/2.png)

You can configure the decoding of several parameters in `config.ini`
> will be created in `<user_home>/arinc_plugin/` after clicking `Ok` with the `Use config` option selected

and save the result in `.csv` files
> the path can be set in `config.ini`

![example](screenshots/3.png)

[on GitLab](https://gitlab.com/Aleksandr-Kai/DSView_ARINC429_Decoder) (forcing to turn on 2fa sucks. ms will kill github)
