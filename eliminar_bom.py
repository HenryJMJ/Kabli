with open('data.json', 'rb') as f:
    data = f.read()
    if data.startswith(b'\xef\xbb\xbf'):  # Esto verifica el BOM
        data = data[3:]  # Elimina el BOM
        with open('data_no_bom.json', 'wb') as new_file:
            new_file.write(data)
