/** @odoo-module */

import { AppointmentCreatePopup } from './popups/appointment_create_popup';
import { AppointmentDetailPopup } from './popups/appointment_detail_popup';
import { PendingItemsListPopup } from './popups/pending_items_list_popup';

import './components/pending_items_button/pending_items_button';
import './components/appointment_calendar_button/appointment_calendar_button';
import './components/appointment_screen_button/appointment_screen_button';
import './screens/product_screen/product_screen';
import './screens/appointment_screen/appointment_screen';


// Register components globally
odoo.define("@ths_medical_pos/popups/appointment_create_popup", () => ({ AppointmentCreatePopup }));
odoo.define("@ths_medical_pos/popups/appointment_detail_popup", () => ({ AppointmentDetailPopup }));
odoo.define("@ths_medical_pos/popups/pending_items_list_popup", () => ({ PendingItemsListPopup }));
