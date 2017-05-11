import sys


def setup(mapper={}):
	lowercase = "ᵃᵇᶜᵈᵉᶠᵍʰᶦʲᵏˡᵐⁿᵒᵖ𝑞ʳˢᵗᵘᵛʷˣʸᶻ"
	lowercase_values = list(range(97, 122+1))
	mapper.update(zip(lowercase_values, lowercase))

	uppercase = "ᴀʙᴄᴅᴇғɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢ"
	uppercase_values = list(range(65, 90+1))
	mapper.update(zip(uppercase_values, uppercase))

	# TO-DO: include punctuation
	return mapper

def convert_char(char, mapper):
	char_value = ord(char)
	if char_value in mapper:
		tiny = mapper[char_value]
	else:
		tiny = char

	return tiny

def convert_string(string, mapper):
	return "".join(map(lambda char: convert_char(char, mapper), string))

if __name__ == "__main__":
	characters_to_tiny = setup()
	input_string = sys.argv[1]  # assumes only one string is passed in
	print(convert_string(input_string, characters_to_tiny))