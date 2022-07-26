
sorted_list=[x for x in range(1, 11)]

def binary_search(list, target):
    first=0
    last=len(sorted_list)-1
    
    while first <= last:
        midpoint=(first + last)//2
        
        if list[midpoint] == target:
            return midpoint
        
        elif list[midpoint] < target:
            first = midpoint + 1
        else: 
            last = midpoint -1

    return None
print(sorted_list)
print(binary_search(sorted_list, 10))