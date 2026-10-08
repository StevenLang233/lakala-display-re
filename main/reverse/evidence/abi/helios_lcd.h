/*
 * Copyright (c) Quectel Wireless Solution, Co., Ltd.All Rights Reserved.
 *  
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *  
 *     http://www.apache.org/licenses/LICENSE-2.0
 *  
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

#ifndef _HELIOS_LCD_H
#define _HELIOS_LCD_H
 
#ifdef __cplusplus
 extern "C" {
#endif


#ifndef bool
#define bool _Bool
#endif

 
 typedef enum {
	HELIOS_SPI_LCD_CLK_812_5K = 812,
	HELIOS_SPI_LCD_CLK_1_625M = 1625,
	HELIOS_SPI_LCD_CLK_3_25M = 3250,
	 HELIOS_SPI_LCD_CLK_6_5M = 6500,
	 HELIOS_SPI_LCD_CLK_13M = 13000,
	 HELIOS_SPI_LCD_CLK_26M = 26000,
	 HELIOS_SPI_LCD_CLK_52M = 52000,
 }Helios_SPILCDCLK;

  typedef struct {
	uint8_t type;		/* SPI_WRITE_CMD / SPI_WRITE_DATA / SPI_WRITE_DELAY */
	uint16_t value;
	uint8_t data_length;	/* Only for SPI_WRITE_CMD */
}Helios_LCDWriteStruct;


typedef enum {
	 HELIOS_LCD_CMD = 0,
	 HELIOS_LCD_DATA,
	 HELIOS_LCD_DELAY,
 }Helios_LCDParaType;

 
 typedef enum {
	 HELIOS_LCD_TYPE_RGB565 = 0,
	 HELIOS_LCD_TYPE_FSTN,
	 HELIOS_LCD_TYPE_RGB666,
	 HELIOS_LCD_TYPE_MIPI,
	 HELIOS_LCD_TYPE_LIMIT,
 }Helios_LCDType;

 typedef enum
{
    INTERFACE_LCD,
    INTERFACE_SPI,
} LCD_INTERFACE;

 
 typedef struct {
	 void* init_data;
	 uint32_t init_data_len;
	 int width;
	 int hight;
	 int clk;
	 int dataline;
	 int linenum;
	 int lcdtype;
	 void *invaild_data;
	 uint32_t invaild_data_len;
	 void *displayon_data;
	 uint32_t displayon_data_len;
	 void *displayoff_data;
	 uint32_t displayoff_data_len;
	 void *light_level_data;
	 uint32_t light_level_data_len;
	 uint8_t te_sel;
	 uint32_t te_pin;
	 uint8_t is_logo_exist;
	 uint8_t init_flag;
 }Helios_LCDInitStruct;


 typedef struct {
	 void* init_data;
	 uint32_t init_data_len;
	 int width;
	 int hight;
	 uint16_t bpp;
	 uint16_t lcd_interface;
	 uint8_t data_lane;
	 uint8_t mipi_mode;
	 uint8_t pixel_format;
	 uint8_t dsi_format;
	 uint8_t trans_mode;
	 uint8_t rgb_order;
	 bool bllp_enable;
	 uint32_t h_sync_active;
	 uint32_t h_back_porch;
	 uint32_t h_front_porch;
	 uint32_t v_sync_active;
	 uint32_t v_back_porch;
	 uint32_t v_front_porch;
	 uint8_t frame_rate;
	 uint8_t te_sel;
	 uint8_t rst_Polarity;
	 uint32_t dsi_pclk_rate;

}Helios_MIPIInitStruct;

typedef struct
{
    int spi_port;
    int spimode;
    uint32_t spiclk;
    int CSPin;
    int DCPin;
    int RSTPin;
	int lcdType;
} QPY_LCDSPI_INFO;
 
 int Helios_LCD_Init(Helios_LCDInitStruct *init_data);
 
 int Helios_LCD_Clear(uint16_t color);
 
 
 int Helios_LCD_Brightness(uint32_t light_level);
 #if defined (PLAT_Unisoc) || defined(PLAT_Unisoc_8850) || defined(PLAT_Unisoc_8910_R05) || defined(PLAT_Unisoc_8850_R02) || defined(PLAT_Unisoc_8910_R06)
 int Helios_LCD_Level_Brightness(uint32_t light_level, uint32_t brightness_level);
 #endif
 int Helios_LCD_Write(void *buffer,uint32_t start_x, uint32_t start_y, uint32_t end_x, uint32_t end_y);
 
 int Helios_LCD_Display_on();
 #if defined (PLAT_ASR_1606) || defined (PLAT_ASR_1609)
 int Helios_LCD_Set_Offset(int offset_x, int offset_y);
 #endif

 int Helios_LCD_Display_off();
 
 int Helios_LCD_WriteCmd(uint64_t cmd, uint32_t data_len);
 
 int Helios_LCD_WriteData(uint64_t  data, uint32_t data_len);
 
 char* Helios_LCD_GetFrameBufferAddr();
 
 int Helios_LCDWriteDataByFile(void* file_name, uint32_t start_x, uint32_t start_y);
 
 int Helios_LCDWriteDataByFileWH(void* file_name, uint32_t start_x, uint32_t start_y,uint32_t width, uint32_t hight);
 
int Helios_LCD_MIPIInit(Helios_MIPIInitStruct *init_data);
int Helios_mipi_lcd_write_area(void *buffer, uint16_t start_x, uint16_t start_y, uint16_t end_x, uint16_t end_y);
int Helios_mipi_LCD_Clear(uint16_t color);

#if defined(BOARD_EC600UCN_LC) || defined(BOARD_EC600UCN_LC_EXTFS8M)  || defined(BOARD_EC600UCN_LC_ZS)
void Helios_LCD_VDD_switch_on(void);

void Helios_LCD_VDD_switch_off(void);
#endif
#if defined (PLAT_Unisoc) || defined(PLAT_Unisoc_8910_R05)|| defined(PLAT_Unisoc_8850_R02) || defined(PLAT_Unisoc_8910_R06)
int Helios_SPI_LCD_Brightness(uint32_t light_level);
#endif

// int QPY_LCD_Set_Interface(LCD_INTERFACE type);
// int QPY_LCD_Init(Helios_LCDInitStruct *init_data, QPY_LCDSPI_INFO spi_info);
// int QPY_LCD_Write(void *buffer, uint32_t start_x, uint32_t start_y, uint32_t end_x, uint32_t end_y);
// int QPY_LCD_Display_on();
// int QPY_LCD_Display_off();
// int QPY_LCD_WriteCmd(uint64_t cmd, uint32_t data_len);
// int QPY_LCD_WriteData(uint64_t data, uint32_t data_len);
// int QPY_LCD_Clear(uint16_t color);

int Helios_LCD_MIPI_DSI_read(char* reg, int reg_len, char *r_data, int r_data_len);

unsigned int Helios_LCD_ReadID(uint8_t cmd);


#ifdef __cplusplus
 } /*"C" */
#endif
 
#endif
 
 
 



