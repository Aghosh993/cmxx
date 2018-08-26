#ifndef REG_H_
#define REG_H_	1

#include <stdint.h>

template<uint32_t addr, uint32_t mask, uint32_t shift, class rw_policy>
struct reg_t {
	static void write(uint32_t val)
	{
		rw_policy::write(reinterpret_cast<volatile uint32_t *>(addr),
							mask,
							shift,
							val);
	}
	
	static uint32_t read(void)
	{
		return rw_policy::read(reinterpret_cast<volatile uint32_t *>(addr),
							mask,
							shift);
	}
};

typedef struct {
	static void write(volatile uint32_t *addr, uint32_t mask, uint32_t shift, uint32_t val)
	{
		*addr = (*addr & ~(mask << shift)) | ((val & mask) << shift);
	}
	static uint32_t read(volatile uint32_t *addr, uint32_t mask, uint32_t shift)
	{
		return (*addr >> shift) & mask;
	}
}rw_t;

typedef struct {
	static void write(volatile uint32_t *addr, uint32_t mask, uint32_t shift, uint32_t val)
	{
		*addr = (*addr & ~(mask << shift)) | ((val & mask) << shift);
	}
}wo_t;

typedef struct {
	static uint32_t read(volatile uint32_t *addr, uint32_t mask, uint32_t shift)
	{
		return (*addr >> shift) & mask;
	}
}ro_t;

#endif