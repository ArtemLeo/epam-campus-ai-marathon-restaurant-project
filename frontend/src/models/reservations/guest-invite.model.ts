/** GET /guest/invites/{token} — PascalCase on purpose: the .NET record is serialised without a naming policy. */
export interface GuestInvite {
  GroupReservationId: string
  LocationId: string
  RestaurantName: string
  LocationAddress: string
  StartTime: string
  EndTime: string
  MaxGuestCount: number
  TableNumber: number
  InviterName: string
}

/** GET /reservations/{reservationId}/invite-token */
export interface GroupInviteToken {
  token: string
}
