import sigrokdecode as srd
import configparser
import os
import csv
import datetime


class SamplerateError(Exception):
    pass


class InternalError(Exception):
    pass


homeDir = os.path.expanduser('~')
defaultConfigPath = os.path.join(homeDir, 'arinc_plugin', 'config.ini')

annBits, annAddr, annId, annData, annMatrix, annParity, annPause, annBitNum, annValue = range(9)

class Decoder(srd.Decoder):
    api_version = 3
    id = 'arinc429'
    name = '0:ARINC 429 v2'
    longname = 'ARINC 429'
    desc = 'ARINC 429 v2'
    license = 'gplv2+'
    inputs = ['logic']
    outputs = ['arinc429']
    tags = ['Embedded/industrial']
    channels = (
        {'id': 'neg', 'name': '"0"', 'desc': '0', 'default': 5},
        {'id': 'pos', 'name': '"1"', 'desc': '1', 'default': 6},
    )

    annotations = (
        ('ann_bit', 'Bit'),
        ('ann_addr', 'Addr'),
        ('ann_id', 'ID'),
        ('ann_data', 'Data'),
        ('ann_matrix', 'Matrix'),
        ('ann_parity', 'Parity'),
        ('ann_pause', 'Pause'),
        ('ann_inf', 'Bit num'),
        ('ann_phys', 'Value'),
    )
    annotation_rows = (
        ('annr_inf', 'Bit num', (annBitNum,)),
        ('annr_bits', 'Bits', (annBits,)),
        ('annr_struct', 'Struct', (annAddr, annId, annData, annMatrix, annParity, annPause)),
        ('annr_phys', 'Value', (annValue,)),
    )
    options = (
        {'id': 'o_calc', 'desc': 'Calc value',
            'default': 'No', 'values': ('Yes', 'No')},
        {'id': 'o_usecfg', 'desc': 'Use config ' + defaultConfigPath,
         'default': 'No', 'values': ('Yes', 'No')},
        {'id': 'o_addr', 'desc': 'Addr (oct)', 'default': 0},
        {'id': 'o_id', 'desc': 'ID', 'default': '0',
            'values': ('0', '1', '2', '3', 'Ignore')},
        {'id': 'o_start', 'desc': 'First bit',
            'default': 11, 'values': tuple(range(11, 29))},
        {'id': 'o_stop', 'desc': 'Last bit (not sign bit)',
            'default': 28, 'values': tuple(range(12, 30))},
        {'id': 'o_sign', 'desc': 'Signed', 'default': 'Unsigned',
            'values': ('Unsigned', 'Signed', 'Two’s complement (DK)')},
        {'id': 'o_msb', 'desc': 'MSB/LSB',
            'default': 'MSB', 'values': ('MSB', 'LSB')},
        {'id': 'o_msbValue', 'desc': 'High order value', 'default': '4096'},
        {'id': 'o_lsbValue', 'desc': 'Low order value', 'default': '1.000000'},
    )

    def __init__(self):
        self.reset()

    def reset(self):
        self.samplerate = None
        self.samplenum = 0
        self.currentParam = None
        self.useConfig = False
        self.config = None

    def start(self):
        self.out_python = self.register(srd.OUTPUT_PYTHON)
        self.out_ann = self.register(srd.OUTPUT_ANN)
        self.useConfig = (self.options['o_usecfg'] == 'Yes')
        if self.useConfig:
            self.config = getConfig(defaultConfigPath)

            if self.config[keySave]:
                os.makedirs(self.config[keyPath], exist_ok=True)
                savePath = os.path.join(
                    self.config[keyPath], datetime.datetime.now().strftime("decode_%H-%M_%m_%d_%Y"))
                os.mkdir(savePath)
                self.saver = Saver(savePath)
                for param in self.config[keyParameters]:
                    self.saver.addSave(param[keyName])

    def metadata(self, key, value):
        if key != srd.SRD_CONF_SAMPLERATE:
            return
        self.samplerate = value

    def calcValue(self, data, ph_start, ph_stop, firstBit, lastBit, signBit, lsbValue):
        _width = lastBit - firstBit + 1  # number of significant bits

        mask = (2**_width*2-1)
        _data = (data >> (firstBit-11)) & mask
        res = _data * lsbValue
        if signBit != Unsigned:
            sign = _data >> _width
            if sign:
                if signBit == Dk:
                    res = (~(_data - 1) &
                           mask) * -lsbValue
                elif signBit == Signed:
                    res = (
                        _data & ~(1 << _width)) * -lsbValue
        self.put(ph_start, ph_stop, self.out_ann, [annValue, ['%f' % res]])
        return res

    def getLsbOption(self):
        _first = self.options['o_start']
        _last = self.options['o_stop']
        _width = _last - _first

        if self.options['o_msb'] == 'MSB':
            return float(self.options['o_msbValue']) / (2**_width)
        return float(
            self.options['o_lsbValue'])

    def getSignOption(self):
        if self.options['o_sign'] == 'Signed':
            return Signed
        if self.options['o_sign'] == 'Unsigned':
            return Unsigned
        return Dk
    # **************************************************************

    def decode(self):  # execute with stream
        if not self.samplerate:
            raise SamplerateError('Cannot decode without samplerate.')

        # waiting for rising edge to measure samples per bit
        self.wait([{0: 'r'}, {1: 'r'}])
        probeSemple = self.samplenum  # store initial sample of probe
        self.wait([{0: 'f'}, {1: 'f'}])  # waitin end of high level
        self.freq = round(1/((self.samplenum - probeSemple)
                          * 2 / self.samplerate) / 1000, 1)  # arinc frequency
        self.put(probeSemple, self.samplenum, self.out_ann,
                 [annBits, ['probe: ' + str(self.freq) + 'kHz']])
        halfbit = self.samplenum - probeSemple
        bitwidth = halfbit * 2

        self.samplenum -= self.samplenum
        probeSemple = 0

        # search word spacing (more than 3 periods)
        while self.samplenum - probeSemple < bitwidth * 3:
            self.wait({0: 'l', 1: 'l'})
            probeSemple = self.samplenum
            self.wait([{0: 'r'}, {1: 'r'}])

        self.samplenum -= halfbit
        self.put(probeSemple, self.samplenum, self.out_ann, [annBits, ['Start']])

        # word_start = 0
        start = 0
        ph_start = 0
        ph_stop = 0

        while True:
            bitcnt = 0
            addr = 0
            raw_addr = 0
            id = 0
            data = 0
            matrix = 0
            parity = 0
            cnt = 0
            while bitcnt < 32:
                (neg, pos) = self.wait([{0: 'h'}, {1: 'h'}])

                if bitcnt < 8:  # read address
                    if bitcnt == 0:
                        start = self.samplenum
                        # word_start = self.samplenum
                    addr = addr << 1
                    addr |= pos
                elif bitcnt < 10:
                    if bitcnt == 8:
                        oct = addr & 0x07
                        oct += ((addr >> 3) & 0x07) * 10
                        oct += ((addr >> 6) & 0x07) * 100
                        raw_addr = addr
                        addr = oct
                        self.put(start, self.samplenum, self.out_ann, [annAddr, ['Addr: %d' % addr, '%d' % addr]])
                        start = self.samplenum
                        cnt = 0
                    id |= pos << cnt
                    cnt += 1
                elif bitcnt < 29:
                    if bitcnt == 10:
                        self.put(start, self.samplenum, self.out_ann, [annId, ['ID: %d' % id, '%d' % id]])
                        start = self.samplenum
                        cnt = 0
                    data |= pos << cnt

                    if self.options['o_calc'] == 'Yes':
                        if self.useConfig:
                            self.currentParam = findParam(
                                self.config[keyParameters], addr, id)
                            if self.currentParam != None:
                                if cnt == self.currentParam[keyFirstBit] - 11:
                                    ph_start = self.samplenum
                                if self.currentParam[keySignBit] != 'unsigned':
                                    if cnt == self.currentParam[keyLastBit] - 11 + 2:
                                        ph_stop = self.samplenum
                                elif cnt == self.currentParam[keyLastBit] - 11 + 1:
                                    ph_stop = self.samplenum
                        else:
                            if self.options['o_addr'] == addr:
                                if (self.options['o_id'] == 'Ignore') or (self.options['o_id'] == str(id)):
                                    if cnt == self.options['o_start'] - 11:
                                        ph_start = self.samplenum
                                    if self.options['o_sign'] != 'Unsigned':
                                        if cnt == self.options['o_stop'] - 11 + 2:
                                            ph_stop = self.samplenum
                                    elif cnt == self.options['o_stop'] - 11 + 1:
                                        ph_stop = self.samplenum
                    cnt += 1
                elif bitcnt < 31:
                    if bitcnt == 29:
                        self.put(start, self.samplenum, self.out_ann, [annData, ['Data: 0x%X' % data, '%X' % data]])
                        ##################################################################
                        if self.options['o_calc'] == 'Yes':
                            if ph_stop < ph_start:
                                ph_stop = self.samplenum
                            if self.useConfig and self.currentParam != None:
                                value = self.calcValue(data, ph_start, ph_stop, self.currentParam[keyFirstBit], self.currentParam[
                                    keyLastBit], self.currentParam[keySignBit], self.currentParam[keyLsbValue])
                                if self.config[keySave]:
                                    if self.currentParam[keyTimeInterval] == 0:
                                        if self.currentParam[keyTimestamp] == 0:
                                            self.currentParam[keyTimestamp] = self.samplenum / \
                                                self.samplerate
                                        else:
                                            self.currentParam[keyTimeInterval] = self.samplenum / \
                                                self.samplerate - \
                                                self.currentParam[keyTimestamp]
                                    self.currentParam[keyTimestamp] += self.currentParam[keyTimeInterval]
                                    self.saver.writeRow(self.currentParam[keyName], [
                                                        self.currentParam[keyTimestamp], value])
                            else:
                                if self.options['o_addr'] == addr:
                                    if (self.options['o_id'] == 'Ignore') or (self.options['o_id'] == str(id)):
                                        self.calcValue(data,
                                                       ph_start, ph_stop, self.options['o_start'], self.options['o_stop'], self.getSignOption(), self.getLsbOption())
                        ##################################################################
                        start = self.samplenum
                        cnt = 0
                    matrix |= pos << cnt
                    cnt += 1
                else:
                    if bitcnt == 31:
                        self.put(start, self.samplenum, self.out_ann, [annMatrix, ['M: %d' % matrix, '%d' % matrix]])
                        start = self.samplenum
                    parity = pos

                probeSemple = self.samplenum
                self.wait([{0: 'r'}, {1: 'r'}, {'skip': bitwidth + halfbit}])
                self.put(probeSemple, self.samplenum, self.out_ann, [annBits, ['%d' % pos]])
                self.put(probeSemple, self.samplenum, self.out_ann, [annBitNum, ['%d' % (bitcnt + 1)]])

                par = 0
                if bitcnt == 31:
                    # self.put(word_start, self.samplenum, self.out_ann, [annValue, ['%X/%X/%X/%X/%X' % (raw_addr,id,data,matrix,parity)]])
                    while raw_addr > 0:
                        raw_addr &= (raw_addr-1)
                        par += 1
                    while id > 0:
                        id &= (id-1)
                        par += 1
                    while data > 0:
                        data &= (data-1)
                        par += 1
                    while matrix > 0:
                        matrix &= (matrix-1)
                        par += 1
                    par += parity

                    par = par % 2
                    if (par != 0):
                        par = 'Er'
                    else:
                        par = 'Ok'
                    self.put(start, self.samplenum, self.out_ann,[annParity, ['P: %s' % par, '%s' % par]])
                    self.currentParam = None
                bitcnt += 1


main_config_section = "main"
main_save_path_key = "saveto"
main_save_key = "save"

param_addr_key = "addr"
param_id_key = "id"
param_first_bit_key = "first_bit"
param_last_bit_key = "last_bit"
param_sign_key = "sign"
param_msb_value_key = "msb_value"
param_lsb_value_key = "lsb_value"

keySave = main_save_key
keyPath = 'savePath'
keyName = 'name'
keyAddr = 'addr'
keyId = 'id'
keyFirstBit = 'first'
keyLastBit = 'last'
keySignBit = 'sign'
keyLsbValue = 'lsb'
keyParameters = 'params'
keyTimeInterval = 'interval'
keyTimestamp = 'timestamp'

Unsigned = 'unsigned'
Signed = 'signed'
Dk = 'dk'


def createConfigExample(path):
    param_name_section = 'param_name'

    ini = configparser.ConfigParser()
    ini.add_section(main_config_section)
    ini.add_section(param_name_section)

    ini[main_config_section][main_save_path_key] = 'path to saves folder'
    ini[main_config_section][main_save_key] = '0 - do not save decodes, 1 - save decodes'
    ini[param_name_section][param_addr_key] = 'number (oct address)'
    ini[param_name_section][param_id_key] = 'number (0-3)'
    ini[param_name_section][param_first_bit_key] = 'number (11-29)'
    ini[param_name_section][param_last_bit_key] = 'number (11-29)'
    ini[param_name_section][param_lsb_value_key] = 'number (lsb prior use in calc)'
    ini[param_name_section][param_msb_value_key] = 'number'
    ini[param_name_section][param_sign_key] = Unsigned + \
        " or " + Signed + " or " + Dk

    os.makedirs(os.path.join(homeDir, 'arinc_plugin'), exist_ok=True)
    with open(path, 'w') as configfile:
        ini.write(configfile)


def getConfig(path=defaultConfigPath):
    ini = configparser.ConfigParser()
    ini.read(path)
    if len(ini.sections()) == 0:
        createConfigExample(path)
        raise InternalError(
            'Config file not found. Example created at ' + path)

    param_names = []
    params = []

    try:
        config = {keyPath: ini[main_config_section][main_save_path_key]}
    except:
        raise InternalError('Can not find save path')

    for section in ini.sections():
        if section != main_config_section:
            param_names.append(section)

    try:
        config[main_save_key] = int(
            ini[main_config_section][main_save_key]) == 1
    except:
        config[main_save_key] = False

    for param in param_names:
        prm = {}
        prm[keyName] = param
        prm[keyTimeInterval] = 0
        prm[keyTimestamp] = 0

        try:
            prm[keyAddr] = int(ini[param][param_addr_key])
            prm[keyId] = int(ini[param][param_id_key])
            prm[keyFirstBit] = int(ini[param][param_first_bit_key])
            prm[keyLastBit] = int(ini[param][param_last_bit_key])
            prm[keySignBit] = ini[param][param_sign_key]
        except:
            continue

        _width = prm[keyLastBit] - prm[keyFirstBit]

        try:
            prm[keyLsbValue] = float(ini[param][param_lsb_value_key])
        except:
            try:
                prm[keyLsbValue] = float(
                    ini[param][param_msb_value_key]) / (2**_width)
            except:
                continue
        params.append(prm)

    config[keyParameters] = params
    return config


def findParam(params, addr, id):
    for param in params:
        if (addr == param[keyAddr]) and (id == param[keyId]):
            return param
    return None


def getParamName(params, addr, id):
    param = findParam(params, addr, id)
    if param != None:
        return param[keyName]
    return ""


class Saver:
    def __init__(self, path: str):
        self.files = {}
        self.path = path

    def addSave(self, name: str):
        f = open(os.path.join(self.path, name + '.csv'), 'w')
        self.files[name] = csv.writer(f, delimiter=';')

    def writeRow(self, name, row):
        if name != "":
            self.files[name].writerow(row)
