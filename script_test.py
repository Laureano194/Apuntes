def findCode(file):
    code = ''
    count = 0
    for char in file:
        if char=='_':
            count+=1
        elif count == 2:
            code += char
    return code

print(findCode('5_0_4_8EqyEK3agP..jpg'))