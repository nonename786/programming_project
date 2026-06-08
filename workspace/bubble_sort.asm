section .data
    arr dd 64, 34, 25, 12, 22, 11, 90  ; 7-element array of 32-bit integers
    len equ ($ - arr) / 4                 ; number of elements

section .text
    global _start

_start:
    ; Bubble sort implementation
    mov ecx, len        ; outer loop counter (n)
outer_loop:
    cmp ecx, 1
    jle done            ; if n <= 1, sorting done
    
    mov ebx, 0          ; inner loop index i = 0
inner_loop:
    cmp ebx, ecx
    jge outer_inc       ; if i >= n, break inner loop
    
    ; load arr[i] and arr[i+1]
    mov eax, [arr + ebx * 4]
    mov edx, [arr + ebx * 4 + 4]
    
    ; compare arr[i] > arr[i+1]
    cmp eax, edx
    jle no_swap
    
    ; swap arr[i] and arr[i+1]
    mov [arr + ebx * 4], edx
    mov [arr + ebx * 4 + 4], eax
no_swap:
    inc ebx
    jmp inner_loop

outer_inc:
    dec ecx
    jmp outer_loop

done:
    ; exit syscall (Linux x86-64)
    mov rax, 60         ; sys_exit
    mov rdi, 0          ; exit status
    syscall
