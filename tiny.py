import sys


_mapper_ = None


def setup(mapper=None, set_mapper=True):
	if not mapper:
		mapper = {}

	lowercase = "ᵃᵇᶜᵈᵉᶠᵍʰᶦʲᵏˡᵐⁿᵒᵖ𝑞ʳˢᵗᵘᵛʷˣʸᶻ"
	lowercase_values = list(range(97, 122+1))
	mapper.update(zip(lowercase_values, lowercase))

	uppercase = "ᴀʙᴄᴅᴇғɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢ"
	uppercase_values = list(range(65, 90+1))
	mapper.update(zip(uppercase_values, uppercase))

	digits = "⁰¹²³⁴⁵⁶⁷⁸⁹"
	digits_values = list(range(48, 57+1))
	mapper.update(zip(digits_values, digits))

	symbols = { 33: "﹗",
				36: "﹩",
				37: "﹪",
				38: "﹠",
				40: "⁽",
				41: "⁾"}

	mapper.update(symbols)

	if set_mapper:
		global _mapper_
		_mapper_ = mapper

	return mapper


def convert_char(char, mapper=None):
	if not mapper:
		mapper = _mapper_

	char_value = ord(char)
	if char_value in mapper:
		tiny = mapper[char_value]
	else:
		tiny = char

	return tiny


def convert_string(string, mapper=None):
	if not mapper:
		mapper = _mapper_

	return "".join(map(lambda char: convert_char(char, mapper), string))

if __name__ == "__main__":
	if len(sys.argv) != 2:
		exit()

	input_string = sys.argv[1]  # assumes only one string is passed in
	setup()
	print(convert_string(input_string))

else:
	setup()