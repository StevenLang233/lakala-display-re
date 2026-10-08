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

/**
 @file	helios_uart.h
 @brief	Data type definition for UART Record.
*/
/**************************************************************************
===========================================================================
Copyright (c) 2018 Quectel Wireless Solution, Co., Ltd.All Rights Reserved.
Quectel Wireless Solution Proprietary and Confidential.
===========================================================================

						EDIT HISTORY FOR FILE
This section contains comments describing changes made to the module.
Notice that changes are listed in reverse chronological order.

WHEN		WHO			WHAT,WHERE,WHY
----------  ---------   ---------------------------------------------------
2021/03/27  Felix.Ye	Create.
**************************************************************************/

#ifndef _HELIOS_UART_H
#define _HELIOS_UART_H


#ifdef __cplusplus
extern "C" {
#endif


/**
 * Serial port baudrate enum
 */
typedef enum
{
	HELIOS_UART_BAUD_300 		 = 300,
	HELIOS_UART_BAUD_600    	 = 600,
    HELIOS_UART_BAUD_1200       = 1200,
    HELIOS_UART_BAUD_2400       = 2400,
	HELIOS_UART_BAUD_3600       = 3600,
    HELIOS_UART_BAUD_4800       = 4800,
	HELIOS_UART_BAUD_7200       = 7200,
    HELIOS_UART_BAUD_9600       = 9600,
    HELIOS_UART_BAUD_14400      = 14400,
    HELIOS_UART_BAUD_19200      = 19200,
    HELIOS_UART_BAUD_28800      = 28800,
    HELIOS_UART_BAUD_33600      = 33600,
    HELIOS_UART_BAUD_38400      = 38400,
    HELIOS_UART_BAUD_57600      = 57600,
    HELIOS_UART_BAUD_115200     = 115200,
    HELIOS_UART_BAUD_230400     = 230400,
    HELIOS_UART_BAUD_460800     = 460800,
    HELIOS_UART_BAUD_921600     = 921600,
	HELIOS_UART_BAUD_1000000	 = 1000000,
	HELIOS_UART_BAUD_1842000	 = 1842000,
	HELIOS_UART_BAUD_3686400	 = 3686400,
	HELIOS_UART_BAUD_4468750    = 4468750
}Helios_UARTBaud;


/**
 * Serial port flow control enum
 */
typedef enum
{
	HELIOS_UART_FC_NONE = 0,
	HELIOS_UART_FC_HW,
}Helios_UARTFlowCtrl;


/**
 * Serial port databit enum
 */
typedef enum 
{
	HELIOS_UART_DATABIT_5 = 5,
	HELIOS_UART_DATABIT_6 = 6,
	HELIOS_UART_DATABIT_7 = 7,
	HELIOS_UART_DATABIT_8 = 8,
}Helios_UARTDataBit;


/**
 * Serial port stopbit enum
 */
typedef enum 
{
	HELIOS_UART_STOP_1 = 1,
	HELIOS_UART_STOP_2 = 2,
}Helios_UARTStopBit;


/**
 * Serial port paritybit enum
 */
typedef enum 
{
	HELIOS_UART_PARITY_NONE = 0,
	HELIOS_UART_PARITY_EVEN = 1,
	HELIOS_UART_PARITY_ODD = 2,
#if defined(PLAT_ASR_1606) || defined(PLAT_ASR_1609) || defined(PLAT_ASR_1602)
	HELIOS_UART_PARITY_MARK = 3,
	HELIOS_UART_PARITY_SPACE = 4,
#endif
}Helios_UARTParityBit;


/**
 * Serial port property configuration
 */
typedef struct 
{
	Helios_UARTBaud baudrate;
	Helios_UARTDataBit data_bit;
	Helios_UARTStopBit stop_bit;
	Helios_UARTParityBit parity_bit;
	Helios_UARTFlowCtrl flow_ctrl;
}Helios_UARTConfig;


/**
 * Uniform channel interface to the PY layer
 */
typedef enum {
	HELIOS_UART0 = 0,
	HELIOS_UART1,
	HELIOS_UART2,
	HELIOS_UART3,
	HELIOS_UART4,
	HELIOS_UART5,
	HELIOS_UART6,
	HELIOS_UARTMAX,
}Helios_UARTNum;

/**
 * The PY layer and the Adapter layer interface transform 
 */
typedef struct {
	Helios_UARTNum export_uart;      //Adapter layer interface for UART
	uint32_t internal_uart;    //Platform layer interface for UART
}Helios_UARTMap;

typedef enum {
	HELIOS_UART_DIREC_UP=0,
	HELIOS_UART_DIREC_DOWN,
}Helios_UART_Direc;




/*****************************************************************
* Description: EC200U UART callback 
* Different platforms need to implement this function according to platform characteristics
* 
* Parameters:
*   ind_type        [in]    Event types, including UART RX receiving data and RX Buffer overflow. 
* 	port	  		[in] 	To the serial port of data 
* 	size	  		[in] 	Data size
*
*****************************************************************/
typedef void (*Helios_UARTCallback)(uint64_t ind_type, Helios_UARTNum port, uint64_t size);


/**
 * Serial initialization structure
 */

typedef struct
{
/**
 * Serial port properties configure the structure
 */
  Helios_UARTConfig *uart_config;
/**
* A callback function that needs to be registered. 
* If it is NULL, cancel the registration of the callback function 
* and use polling to read the data
*/
  Helios_UARTCallback uart_callback;
  
} Helios_UARTInitStruct;



/**
 * @brief:
 *      uart open init
 *
 * @param:
 *		\uart_port         [in] uart port
 *      \uart_para         [in] Serial initialization structure
 *
 * @return:
 *     uart open init result, 0 for success,-1 for failure
 */
int Helios_UART_Init(Helios_UARTNum uart_port,Helios_UARTInitStruct *uart_para);


/**
 * @brief:
 *     close uart
 *
 * @param:
 *		\port       [in] uart port
 * @return:
 *     close uart result, 0 for success,-1 for failure
 */
int Helios_UART_Deinit(Helios_UARTNum port);


/**
 * @brief:
 *      write data to uart
 *
 * @param:
 *		\port          [in] uart port 
 *		\data          [in] data written to the UART serial port
 *		\len           [in] the length of data written to the UART serial port
 * @return:
 *      write data result
 */
int Helios_UART_Write(Helios_UARTNum port, void *data, size_t len);


/**
 * @brief:
 *      read data from uart
 *
 * @param:
 *		\port          [in]  uart port
 *		\data          [out] data read from the UART
 *		\len      	   [in]  the length of data read from the UART serial port
 * @return:
 *      read data result
 */
int Helios_UART_Read(Helios_UARTNum port, void *data, size_t len);


int Helios_UART_SetCallback(Helios_UARTNum port, Helios_UARTCallback uart_callback);

int Helios_UART_Any(Helios_UARTNum port);

int Helios_UART_SetCtl_485(Helios_UARTNum port,size_t gpio_in,Helios_UART_Direc direc);

int Helios_UART_SetBlockMode_485(char set);

int Helios_PYLOG_CHANGE_TO_DBG(int param);
#if defined(PLAT_ASR_1803s) || defined(PLAT_ASR_1803sc)
int Helios_Uart_Disable_Rx(Helios_UARTNum port,uint8_t set_value);	
#endif

/**
 * @brief:
 *     check if uart is sending
 *
 * @param:
 *		\port       [in] uart port
 * @return:
 *     0, not sending.
 *     1, is sending.
 *    -1, port not support
 */
int Helios_UART_IsSending(Helios_UARTNum port);

#ifdef __cplusplus
} /*"C" */
#endif

#endif
