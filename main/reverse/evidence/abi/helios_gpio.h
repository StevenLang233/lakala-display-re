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
 @file	helios_gpio.h
 @brief	Data type definition for GPIO.
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
2021/03/29  Felix.Ye	Create.
**************************************************************************/

#ifndef _HELIOS_GPIO_H
#define _HELIOS_GPIO_H

#ifdef __cplusplus
extern "C" {
#endif

#include "helios_pin.h"

/**
 * GPIO direction
 */
typedef enum
{
    HELIOS_GPIO_INPUT,
    HELIOS_GPIO_OUTPUT
}Helios_GPIODir;

/**
 * GPIO output level
 */
typedef enum
{
    HELIOS_LVL_LOW,
    HELIOS_LVL_HIGH
}Helios_LvlMode;

/**
 * GPIO input pull mode
 */
#ifndef HELIOS_PULL_MODE
#define HELIOS_PULL_MODE 1
typedef enum
{
    HELIOS_PULL_NONE,
    HELIOS_PULL_UP,
    HELIOS_PULL_DOWN
}Helios_PullMode;
#endif


typedef enum
{
    HELIOS_GPIO_BLINK_OFF,
    HELIOS_GPIO_BLINK_ON
}Helios_GPIOBlinkSwitch;
	

/**
 * The PY layer and the Adapter layer interface transform 
 */
typedef struct {
	Helios_GPIONum export_pin;      //Adapter layer interface for GPIO
	uint32_t internal_pin;    //Platform layer interface for GPIO
}Helios_GPIOPinMap;

typedef struct
{
  Helios_GPIODir dir;
  Helios_PullMode pull;
  Helios_LvlMode value;
} Helios_GPIOInitStruct;



/**
 * @brief:
 *      gpio init
 *
 * @param:
 *      \gpio_num   	[in]   - gpio number
 *      \gpio_struct    [in]   - Initialized configuration parameter structure
 *
 * @return:
 *      gpio init result,0 for success,-1 for failure
 */
int Helios_GPIO_Init(Helios_GPIONum gpio_num, Helios_GPIOInitStruct *gpio_struct);

/**
 * @brief:
 *      gpio deinit
 *
 * @param:
 *      \gpio_num   	[in]   - gpio number
 *
 * @return:
 *     gpio deinit result,0 for success,-1 for failure
 */
int Helios_GPIO_Deinit(Helios_GPIONum gpio_num);



/**
 * @brief:
 *      get gpio level
 *
 * @param:
 *      \gpio_num     [in]      - gpio number
 *      \p_pin_level  [out]   - get io level
 *
 * @return:
 *      gpio get level result,0 or 1 for success,-1 for failure
 */
int Helios_GPIO_GetLevel(Helios_GPIONum gpio_num);


/**
 * @brief:
 *     set gpio level
 *
 * @param:
 *      \gpio_num   [in]    - gpio number
 *      \pin_level  [in]    - set io level to low or high
 *
 * @return:
 *      gpio set level result,0 for success,-1 for failure
 */
int Helios_GPIO_SetLevel(Helios_GPIONum gpio_num, Helios_LvlMode pin_level);

/**
 * @brief:
 *     set gpio direction
 *
 * @param:
 *      \gpio_num   [in]    - gpio number
 *      \dircetion  [in]    - set io dircetion to in or out
 *
 * @return:
 *      gpio set direction result,0 for success,-1 for failure
 */
int Helios_GPIO_SetDirection(Helios_GPIONum gpio_num, Helios_GPIODir direction);

/**
 * @brief:
 *     get gpio direction
 *
 * @param:
 *      \gpio_num   [in]    - gpio number
 *
 * @return:
 *      gpio get direction result,0 or 1 for success,-1 for failure
 */
int Helios_GPIO_GetDirection(Helios_GPIONum gpio_num);

#if defined (PLAT_Unisoc) || defined(PLAT_Unisoc_8910_R05) || defined(PLAT_Unisoc_8910_R06)
int Helios_pin_cfg_init();
#endif
    
int Helios_netlight_enable(int param);
    
int Helios_netlight_state_get(void);

#ifdef __cplusplus
} /*"C" */
#endif

#endif



