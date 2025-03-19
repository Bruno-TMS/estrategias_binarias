def check_str(value:str):
        if value and isinstance(value, str):
            return value
        else:
            raise ValueError(f'{value} não é uma str válida.')


def check_duration(digit:str, unit:str, lst_units):
    
    if (not digit) and (not unit):
        return '',''
    
    if ((not digit) and unit) or (digit and (not unit)):
        raise ValueError(f'O valor de digit:{digit} unit:{unit} é inválido por apresentar termos vazios.')
    
    if (unit not in lst_units):
        raise ValueError(f'O valor de unit:{unit}, é inválido por não pertencer a lista:{lst_units}')
    
    try:
        dgt = int(digit)
        if dgt <= 0:
            raise ValueError(f'O valor de digit:{dgt} é inválido por apresentar um valor negativo.')
        
    except ValueError as e:
        print(f'Error in check_duration. {e}')
    
    else:
        return dgt, unit