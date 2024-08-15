import sigrokdecode as srd

class SamplerateError(Exception):
	pass

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
		('annr_inf', 'Bit num', (7,)),
		('annr_bits', 'Bits', (0,)),
		('annr_struct', 'Struct', (1, 2, 3, 4, 5, 6)),
		('annr_phys', 'Value', (8,)),
	)
	options = (
		{'id': 'o_calc', 'desc': 'Calc value', 'default': 'No', 'values': ('Yes', 'No')},
		{'id': 'o_addr', 'desc': 'Addr (oct)', 'default': 0},
		{'id': 'o_id', 'desc': 'ID', 'default': '0', 'values': ('0', '1', '2', '3', 'Ignore')},
		{'id': 'o_start', 'desc': 'First bit', 'default': 11, 'values': tuple(range(11, 29))},
		{'id': 'o_stop', 'desc': 'Last bit', 'default': 28, 'values': tuple(range(12, 30))},
		{'id': 'o_sign', 'desc': 'Signed', 'default': 'Unsigned', 'values': ('Unsigned', 'Signed', 'Two’s complement (DK)')},
		{'id': 'o_msb', 'desc': 'MSB/LSB', 'default': 'MSB', 'values': ('MSB', 'LSB')},
		{'id': '0_msbValue', 'desc': 'High order value', 'default': 4096},
		{'id': '0_lsbValue', 'desc': 'Low order value', 'default': 1.00},
	)

	def __init__(self):
		self.reset()

	def reset(self): 
		self.samplerate = None
		self.samplenum = 0

	def start(self):
		self.out_python = self.register(srd.OUTPUT_PYTHON)
		self.out_ann = self.register(srd.OUTPUT_ANN)

	def metadata(self, key, value):
		if key != srd.SRD_CONF_SAMPLERATE:
			return
		self.samplerate = value
			
	#**************************************************************
	def decode(self):
		if not self.samplerate:
			raise SamplerateError('Cannot decode without samplerate.')
		samplerate = float(self.samplerate)
		ss = self.samplenum
		
		self.wait([{0: 'r'}, {1: 'r'}])
		#self.put(0, self.samplenum, self.out_ann, [0, ['s']])
		p = self.samplenum
		self.wait([{0: 'f'}, {1: 'f'}])
		self.put(p, self.samplenum, self.out_ann, [0, ['probe']])
		halfbit = self.samplenum - p
		bitwidth = halfbit * 2
		
		self.samplenum -= self.samplenum
		p = 0
		
		while self.samplenum - p < bitwidth * 3:
			self.wait({0: 'l', 1: 'l'})
			p = self.samplenum
			self.wait([{0: 'r'}, {1: 'r'}])
		
		self.samplenum -= halfbit
		self.put(p, self.samplenum, self.out_ann, [0, ['Start']])
		
		start = 0
		ph_start = 0
		ph_stop = 0
		
		while True:
			bitcnt = 0
			addr = 0
			id = 0
			data = 0
			matrix = 0
			parity = 0
			cnt = 0
			while bitcnt < 32:
				(neg, pos) = self.wait([{0: 'h'}, {1: 'h'}])
				
				if bitcnt < 8:
					if bitcnt == 0:
						start = self.samplenum
					addr = addr << 1
					addr |= pos
				elif bitcnt < 10:
					if bitcnt == 8:
						oct = addr & 0x07
						oct += ((addr >> 3) & 0x07) * 10
						oct += ((addr >> 6) & 0x07) * 100
						addr = oct
						self.put(start, self.samplenum, self.out_ann, [1, ['Addr: %d' % addr, '%d' % addr]])
						start = self.samplenum
						cnt = 0
					id |= pos << cnt
					cnt += 1
				elif bitcnt < 29:
					if bitcnt == 10:
						self.put(start, self.samplenum, self.out_ann, [2, ['ID: %d' % id, '%d' % id]])
						start = self.samplenum
						cnt = 0
					data |= pos << cnt
					
					if self.options['o_calc'] == 'Yes':
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
						self.put(start, self.samplenum, self.out_ann, [3, ['Data: 0x%X' % data, '%X' % data]])
						if self.options['o_calc'] == 'Yes':
							if self.options['o_addr'] == addr:
								if (self.options['o_id'] == 'Ignore') or (self.options['o_id'] == str(id)):
									##################################################################
									if ph_stop < ph_start:
										ph_stop = self.samplenum
									_first = self.options['o_start']
									_last = self.options['o_stop']
									_width = _last - _first + 1  # number of significant bits
									
									if self.options['o_msb'] == 'MSB':
										lsbValue = self.options['0_msbValue'] * 2 / (2**(_width-1))
									else:
										lsbValue = self.options['0_lsbValue']
										
									
									mask = (2**_width*2-1)
									data = (data >> (_first-11)) & mask
									res = data * lsbValue
									if self.options['o_sign'] != 'Unsigned':
										sign = data >> _width
										if sign:
											if self.options['o_sign'] == 'Two’s complement (DK)':
												res = (~(data - 1)&mask)* -lsbValue
											elif self.options['o_sign'] == 'Signed':
												res = (data & ~(1 << (_width+1)))* -lsbValue
									##################################################################
									self.put(ph_start, ph_stop, self.out_ann, [8, ['%f' % res]])
						start = self.samplenum
						cnt = 0
					matrix |= pos << cnt
					cnt += 1
				else:
					if bitcnt == 31:
						self.put(start, self.samplenum, self.out_ann, [4, ['M: %d' % matrix, '%d' % matrix]])
						start = self.samplenum
					parity = pos
				
				p = self.samplenum
				self.wait([{0: 'r'}, {1: 'r'}, {'skip': bitwidth + halfbit}])
				self.put(p, self.samplenum, self.out_ann, [0, ['%d' % pos]])
				self.put(p, self.samplenum, self.out_ann, [7, ['%d' % (bitcnt + 1)]])
				
				par = 0
				if bitcnt == 31:
					while addr > 0:
						addr &= (addr-1)
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
					
					par = par % 2
					if ((par == 0) and (parity != 0)) or ((par != 0) and (parity == 0)):
						par = 'Er'
					else:
						par = 'Ok'
					self.put(start, self.samplenum, self.out_ann, [5, ['P: %s' % par, '%s' % par]])
				bitcnt += 1
		
		
		
		