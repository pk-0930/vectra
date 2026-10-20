import { createContext, useContext } from 'react'
import type { OrganizationContext } from '../types/auth'

export const BusinessContext = createContext<OrganizationContext | null>(null)
export function useBusiness() { return useContext(BusinessContext) }
